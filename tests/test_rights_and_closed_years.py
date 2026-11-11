"""Mike's calls after the 2026-11 security review: mailing the statement
takes the right to book, a closed year's annual accounts stay as they were
closed, and a budget's owner sees their budget, not the club's other
bookings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from hubra.core.models.finance import Transaction, TransactionCategory

URL = "/api/v1/finance"


def test_statement_mail_needs_the_right_to_book(
    client, seeded_db, permissioned_member_factory
):
    viewer = permissioned_member_factory(["finance.overview.read"])
    resp = client.post(f"{URL}/statement/send", json={}, headers=viewer)
    assert resp.status_code == 403
    # Reading it stays with the overview right.
    assert client.get(f"{URL}/statement.pdf", headers=viewer).status_code == 200


@pytest.fixture
def books(db, seeded_db):
    fees = TransactionCategory(name="Mitgliederbeiträge", color="#111111")
    misc = TransactionCategory(name="Diverses", color="#333333")
    db.session.add_all([fees, misc])
    db.session.flush()
    for day, amount, kind, cat in (
        (date(2025, 2, 1), "3000", "income", fees),
        (date(2025, 5, 1), "100", "expense", misc),
        (date(2026, 2, 1), "1000", "income", fees),
    ):
        db.session.add(
            Transaction(
                date=day,
                description="x",
                amount=Decimal(amount) if kind == "income" else -Decimal(amount),
                type=kind,
                method="IBAN",
                status="Completed",
                category_id=cat.id,
            )
        )
    db.session.commit()
    return {"fees": fees, "misc": misc}


def _line(rows, number):
    return next((r for r in rows if r["number"] == number), None)


def test_closed_year_keeps_its_report(client, auth_headers, books):
    assert client.post(f"{URL}/annual/2025/close").status_code == 200
    before = client.get(f"{URL}/annual/2025").get_json()
    assert _line(before["income"], "3000")["amount"] == 3000

    # Move the fee category to "Spenden" and rename the account.
    chart = client.get(f"{URL}/accounts").get_json()
    gifts = next(a for a in chart["accounts"] if a["number"] == "3100")
    fees_acc = next(a for a in chart["accounts"] if a["number"] == "3000")
    client.put(
        f"{URL}/accounts/categories/{books['fees'].id}", json={"accountId": gifts["id"]}
    )
    client.patch(f"{URL}/accounts/{fees_acc['id']}", json={"name": "Neu"})

    after = client.get(f"{URL}/annual/2025").get_json()
    assert after == before
    assert client.get(f"{URL}/annual/2025.pdf").status_code == 200

    # The next year compares with the frozen figures.
    nxt = client.get(f"{URL}/annual/2026").get_json()
    assert _line(nxt["income"], "3000")["previous"] == 3000
    assert _line(nxt["income"], "3100")["amount"] == 1000

    # Reopened, it follows the books again.
    assert client.post(f"{URL}/annual/2025/reopen").status_code == 200
    live = client.get(f"{URL}/annual/2025").get_json()
    assert _line(live["income"], "3100")["amount"] == 3000
    assert _line(live["income"], "3000") is None


def test_year_closed_before_reports_were_stored(client, auth_headers, books, db):
    from hubra_finances.models import YearReport

    assert client.post(f"{URL}/annual/2025/close").status_code == 200
    db.session.query(YearReport).delete()
    db.session.commit()
    first = client.get(f"{URL}/annual/2025").get_json()
    assert db.session.query(YearReport).count() == 1
    assert client.get(f"{URL}/annual/2025").get_json() == first


def test_budget_owner_sees_their_lines_only(client, db, seeded_db, auth_headers):
    from tests.authz.conftest import _create_member_with_role, _login_member

    fees = TransactionCategory(name="Fees")
    other = TransactionCategory(name="Other")
    db.session.add_all([fees, other])
    db.session.flush()
    db.session.add(
        Transaction(
            date=date(2026, 3, 1),
            description="x",
            amount=Decimal("50"),
            type="income",
            method="IBAN",
            status="Completed",
            category_id=other.id,
        )
    )
    db.session.commit()
    lead, _ = _create_member_with_role(
        "owner@test.ch", "Teamleitung", seeded_db["tier"].id, permission_keys=[]
    )
    bid = client.post(
        "/api/v1/budgets/",
        json={
            "name": "Team",
            "year": 2026,
            "owner_id": lead.id,
            "lines": [{"category_id": fees.id, "kind": "income", "planned": 10}],
        },
    ).get_json()["id"]
    assert client.get(f"/api/v1/budgets/{bid}").get_json()["unplanned"]

    _login_member(client, "owner@test.ch")
    mine = client.get(f"/api/v1/budgets/{bid}")
    assert mine.status_code == 200
    assert "unplanned" not in mine.get_json()
    assert len(mine.get_json()["lines"]) == 1
