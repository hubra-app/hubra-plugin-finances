"""Each invoice books its income here: created, paid, changed and deleted
invoices keep their linked transaction in step (hubra_finances.bookings)."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.finance import Transaction, TransactionCategory
from tests.finance.test_invoices import _invoice_payload
from tests.finance.test_invoices_external import (
    _ext_invoice_payload,
    _ext_party,
    _member_invoice_payload,
)


@pytest.fixture
def membership_category(db):
    """TransactionCategory named 'Membership' for the auto-link path."""
    cat = TransactionCategory(name="Membership", color="#00aaff")
    db.session.add(cat)
    db.session.commit()
    return cat


def _create_invoice(client, auth_headers, member_id, amount=100.0):
    return client.post(
        "/api/v1/finance/invoices",
        json={
            "member_id": member_id,
            "issued": date.today().isoformat(),
            "due": date.today().isoformat(),
            "amount": amount,
        },
        headers=auth_headers,
    )


def test_create_invoice_auto_creates_pending_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """POST /invoices creates a Pending transaction and links it."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id, amount=150.0)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None

    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx is not None
    assert tx.status == "Pending"
    assert tx.type == "income"
    assert tx.method == "IBAN"
    assert float(tx.amount) == 150.0
    assert tx.member_id == member_id
    assert tx.description == f"Invoice #{body['id']}"


def test_create_invoice_links_membership_category(
    client, db, auth_headers, seeded_db, membership_category
):
    """The auto-created transaction uses the Membership category."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx.category_id == membership_category.id


def test_create_invoice_falls_back_to_any_category(client, db, auth_headers, seeded_db):
    """Without a Membership category, fall back to the first available category."""
    fallback = TransactionCategory(name="General", color="#aabbcc")
    db.session.add(fallback)
    db.session.commit()

    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None
    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx.category_id == fallback.id


def test_create_invoice_no_category_skips_transaction(
    client, db, auth_headers, seeded_db
):
    """If no categories exist at all, invoice is still created (no transaction_id)."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is None


def test_patch_invoice_paid_completes_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """PATCH /invoices/{id} status=Paid completes the linked transaction."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.get_json()["id"]
    tx_id = create_resp.get_json()["transaction_id"]
    assert tx_id is not None

    patch_resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Paid"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200

    tx = db.session.get(Transaction, tx_id)
    assert tx.status == "Completed"


def test_patch_invoice_non_paid_does_not_complete_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """PATCH /invoices/{id} with a status other than Paid leaves transaction Pending."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.get_json()["id"]
    tx_id = create_resp.get_json()["transaction_id"]

    patch_resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Open"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200

    tx = db.session.get(Transaction, tx_id)
    assert tx.status == "Pending"


def test_get_transactions_shows_pending_entry_after_invoice_create(
    client, db, auth_headers, seeded_db, membership_category
):
    """GET /transactions lists the auto-created Pending entry after invoice creation."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id, amount=200.0)
    assert create_resp.status_code == 201
    tx_id = create_resp.get_json()["transaction_id"]

    list_resp = client.get("/api/v1/finance/transactions", headers=auth_headers)
    assert list_resp.status_code == 200
    tx_ids = [t["id"] for t in list_resp.get_json()["data"]]
    assert tx_id in tx_ids


def test_pending_transaction_excluded_from_overview_balance(
    client, db, auth_headers, seeded_db, membership_category
):
    """GET /finance/overview balance excludes Pending transactions (S03 filter)."""
    member_id = seeded_db["admin"].id

    # Capture baseline balance before creating invoice
    baseline = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert baseline.status_code == 200
    baseline_balance = baseline.get_json()["balance"]

    # Create an invoice — auto-creates a Pending transaction of 250.0
    resp = _create_invoice(client, auth_headers, member_id, amount=250.0)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None  # transaction was created

    # Balance must not change — Pending transactions are excluded
    overview = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert overview.status_code == 200
    assert overview.get_json()["balance"] == baseline_balance


def test_delete_transaction_of_a_mailed_invoice(client, auth_headers, seeded_db, db):
    """Deleting a transaction only unlinks its invoice: the invoice stays,
    open, with its send history."""
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
    from hubra.core.models.invoice_reminder import InvoiceReminderHistory

    category = TransactionCategory(name="Beiträge", color="#123456")
    db.session.add(category)
    db.session.flush()
    tx = Transaction(
        category_id=category.id,
        date=date.today(),
        description="Beitrag",
        method="Bank Transfer",
        amount=Decimal("45.00"),
        type="income",
        status="Pending",
    )
    db.session.add(tx)
    db.session.flush()
    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=date.today(),
        due=date.today() + timedelta(days=30),
        amount=Decimal("45.00"),
        status="Open",
        transaction_id=tx.id,
    )
    db.session.add(invoice)
    db.session.flush()
    db.session.add(
        InvoiceReminderHistory(
            invoice_id=invoice.id,
            reminder_type="generation",
            recipient_email="admin@test.ch",
            recipient_name="Test Admin",
        )
    )
    db.session.commit()
    tx_id, invoice_id = tx.id, invoice.id

    resp = client.delete(f"/api/v1/finance/transactions/{tx_id}", headers=auth_headers)
    assert resp.status_code == 204

    db.session.expunge_all()
    assert db.session.get(Transaction, tx_id) is None
    invoice = db.session.get(Invoice, invoice_id)
    assert invoice is not None
    assert invoice.transaction_id is None
    assert invoice.status == "Open"
    assert (
        db.session.query(InvoiceReminderHistory).filter_by(invoice_id=invoice_id).count()
        == 1
    )


def _invoice_with_transaction(client, auth_headers, seeded_db, db):
    from hubra.core.models.finance import Invoice, TransactionCategory

    db.session.add(TransactionCategory(name="Membership", color="#123456"))
    db.session.commit()
    created = client.post(
        "/api/v1/finance/invoices",
        json=_invoice_payload(seeded_db["admin"].id),
        headers=auth_headers,
    )
    assert created.status_code == 201
    invoice = db.session.get(Invoice, created.get_json()["id"])
    assert invoice.transaction_id is not None
    return invoice.id, invoice.transaction_id


def test_linked_transaction_follows_invoice_status(client, auth_headers, seeded_db, db):
    """Paid completes the linked income; taking the payment back (Paid →
    Open) makes it pending again, so the balance drops it."""
    from hubra.core.models.finance import Transaction

    invoice_id, tx_id = _invoice_with_transaction(client, auth_headers, seeded_db, db)
    url = f"/api/v1/finance/invoices/{invoice_id}"

    assert client.patch(url, json={"status": "Paid"}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(Transaction, tx_id).status == "Completed"

    assert client.patch(url, json={"status": "Open"}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(Transaction, tx_id).status == "Pending"


def test_linked_transaction_follows_invoice_amount(client, auth_headers, seeded_db, db):
    """A corrected amount reaches the pending income; once paid, the booked
    transaction keeps what was paid."""
    from hubra.core.models.finance import Transaction

    invoice_id, tx_id = _invoice_with_transaction(client, auth_headers, seeded_db, db)
    url = f"/api/v1/finance/invoices/{invoice_id}"

    assert client.patch(url, json={"amount": 60.0}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    assert float(db.session.get(Transaction, tx_id).amount) == 60.0

    client.patch(url, json={"status": "Paid"}, headers=auth_headers)
    assert client.patch(url, json={"amount": 70.0}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    tx = db.session.get(Transaction, tx_id)
    assert tx.status == "Completed"
    assert float(tx.amount) == 60.0


def test_overview_open_invoice_amount_is_a_number(client, auth_headers, seeded_db, db):
    """The overview's open-invoice total is a JSON number like its other
    figures (a Decimal went out as the string "45.00")."""
    from hubra.core.models.finance import Invoice

    db.session.add(
        Invoice(
            member_id=seeded_db["admin"].id,
            issued=date.today(),
            due=date.today() + timedelta(days=30),
            amount=Decimal("45.00"),
            status="Open",
        )
    )
    db.session.commit()

    body = client.get("/api/v1/finance/overview", headers=auth_headers).get_json()
    assert body["openInvoices"] == {"count": 1, "amount": 45.0}


def test_linked_income_follows_the_recipient(client, auth_headers, seeded_db, db):
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory

    db.session.add(TransactionCategory(name="Membership", color="#2596be"))
    db.session.commit()
    first = _ext_party(client, auth_headers, name="Erste AG")
    second = _ext_party(client, auth_headers, name="Zweite AG", email="z@example.com")
    invoice_id = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(first["id"]),
        headers=auth_headers,
    ).get_json()["id"]
    tx_id = db.session.get(Invoice, invoice_id).transaction_id
    url = f"/api/v1/finance/invoices/{invoice_id}"

    resp = client.patch(url, json={"external_party_id": second["id"]}, headers=auth_headers)
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Transaction, tx_id).payee_name == "Zweite AG"

    admin_id = seeded_db["admin"].id
    resp = client.patch(
        url,
        json={"member_id": admin_id, "external_party_id": None},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    db.session.expire_all()
    tx = db.session.get(Transaction, tx_id)
    assert (tx.member_id, tx.payee_name) == (admin_id, None)


def test_generate_invoices_creates_pending_transaction(app, billable_tier_db):
    """Task creates a Pending income transaction linked to the invoice."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
    from hubra.core.extensions import db

    with app.app_context():
        cat = TransactionCategory(name="Membership", color="#00aaff")
        db.session.add(cat)
        db.session.commit()

        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = generate_invoices_task.run()
        assert result["created"] >= 1

        invoice = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_billed"].id
            )
        ).one()
        assert invoice.transaction_id is not None

        tx = db.session.get(Transaction, invoice.transaction_id)
        assert tx is not None
        assert tx.status == "Pending"
        assert tx.type == "income"
        assert tx.method == "IBAN"
        assert float(tx.amount) == 99.0
        assert tx.member_id == billable_tier_db["member_billed"].id
        assert tx.description == f"Invoice #{invoice.id}"
        assert tx.category_id == cat.id


def test_create_member_invoice_purpose_other_with_category(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Events", color="#27ae60")
    db.session.add(cat)
    db.session.commit()

    resp = client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(
            seeded_db["admin"].id, purpose="other", category_id=cat.id, amount=30.0
        ),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["purpose"] == "other"

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, body["id"])
    db.session.get(
        TransactionCategory, inv.transaction.id if inv.transaction_id else None
    )
    assert inv.transaction is not None
    assert inv.transaction.category_id == cat.id


def test_create_member_invoice_purpose_membership_default_category(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Membership", color="#2596be")
    db.session.add(cat)
    db.session.commit()

    resp = client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(seeded_db["admin"].id, purpose="membership"),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["purpose"] == "membership"

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, body["id"])
    assert inv.transaction is not None
    assert inv.transaction.category_id == cat.id


def test_create_external_invoice_linked_tx_has_payee_name(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Membership", color="#2596be")
    db.session.add(cat)
    db.session.commit()

    ext = _ext_party(client, auth_headers, name="Linked Co")
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    inv_id = resp.get_json()["id"]

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, inv_id)
    assert inv.transaction is not None
    assert inv.transaction.payee_name == "Linked Co"
    assert inv.transaction.member_id is None
