"""finance.budgets: plan per category and year, actuals from transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.helpers import set_modules
from hubra.core.models.finance import Transaction, TransactionCategory


@pytest.fixture
def cats(db, seeded_db):
    fees = TransactionCategory(name="Fees")
    hall = TransactionCategory(name="Hall rent")
    db.session.add_all([fees, hall])
    db.session.commit()
    return fees, hall


def _tx(db, cat, kind, amount, day, status="Completed"):
    db.session.add(
        Transaction(
            date=day,
            description="x",
            category_id=cat.id,
            amount=Decimal(amount),
            method="IBAN",
            type=kind,
            status=status,
        )
    )


def _create(client, cats, year=2026):
    fees, hall = cats
    return client.post(
        "/api/v1/budgets/",
        json={
            "name": "Club",
            "year": year,
            "lines": [
                {"category_id": fees.id, "kind": "income", "planned": 5000},
                {"category_id": hall.id, "kind": "expense", "planned": "1200.50"},
            ],
        },
    )


def test_budget_with_actuals(client, db, auth_headers, cats):
    fees, hall = cats
    _tx(db, fees, "income", "3000", date(2026, 3, 1))
    _tx(db, fees, "income", "500", date(2026, 4, 1), status="Pending")
    _tx(db, fees, "income", "999", date(2025, 4, 1))
    _tx(db, hall, "expense", "400", date(2026, 5, 1))
    other = TransactionCategory(name="Drinks")
    db.session.add(other)
    db.session.flush()
    _tx(db, other, "expense", "80", date(2026, 6, 1))
    db.session.commit()

    resp = _create(client, cats)
    assert resp.status_code == 201
    body = resp.get_json()
    by_kind = {line["kind"]: line for line in body["lines"]}
    assert by_kind["income"]["planned"] == "5000.00"
    assert by_kind["income"]["actual"] == "3000.00"
    assert by_kind["expense"]["actual"] == "400.00"
    assert body["plannedResult"] == "3799.50"
    assert body["actualResult"] == "2600.00"
    assert body["unplanned"] == [
        {
            "categoryId": other.id,
            "categoryName": "Drinks",
            "kind": "expense",
            "actual": "80.00",
        }
    ]
    listed = client.get("/api/v1/budgets/").get_json()
    assert listed[0]["totals"]["income"] == {"planned": "5000.00", "actual": "3000.00"}


def test_budget_validation(client, auth_headers, cats):
    fees, _ = cats
    assert client.post("/api/v1/budgets/", json={"year": 2026}).status_code == 400
    assert client.post("/api/v1/budgets/", json={"name": "x"}).status_code == 400
    assert (
        client.post("/api/v1/budgets/", json={"name": 5, "year": 2026}).status_code
        == 400
    )
    assert _create(client, cats).status_code == 201
    assert _create(client, cats).status_code == 409
    bid = client.get("/api/v1/budgets/").get_json()[0]["id"]
    bad = [
        [{"category_id": 9999, "kind": "income", "planned": 1}],
        [{"category_id": fees.id, "kind": "gift", "planned": 1}],
        [{"category_id": fees.id, "kind": "income", "planned": -1}],
        [{"category_id": fees.id, "kind": "income", "planned": "abc"}],
        [{"category_id": fees.id, "kind": "income", "planned": "NaN"}],
        [{"category_id": fees.id, "kind": "income", "planned": "1e12"}],
        [{"category_id": fees.id, "kind": "income", "planned": 1}] * 2,
    ]
    for lines in bad:
        resp = client.put(f"/api/v1/budgets/{bid}/lines", json={"lines": lines})
        assert resp.status_code == 400, lines


def test_budget_texts_and_ids_are_checked(client, auth_headers, cats):
    """Wrong types and over-long texts are a 400, never a database error."""
    fees, _ = cats
    for body in (
        {"name": "a", "year": 2026, "notes": {"x": 1}},
        {"name": "x" * 121, "year": 2026},
        {"name": "a", "year": 2026, "notes": "n" * 10_001},
    ):
        assert client.post("/api/v1/budgets/", json=body).status_code == 400, body
    bid = _create(client, cats).get_json()["id"]
    assert client.patch(f"/api/v1/budgets/{bid}", json={"notes": ["x"]}).status_code == 400
    assert client.patch(f"/api/v1/budgets/{bid}", json={"name": "x" * 121}).status_code == 400
    assert client.patch(f"/api/v1/budgets/{bid}", json={"approved": 1}).status_code == 400
    line = {"kind": "income", "planned": 1}
    bad = [
        [{**line, "category_id": True}],
        [{**line, "category_id": float(fees.id)}],
        [{**line, "category_id": fees.id, "note": {"a": 1}}],
        [{**line, "category_id": fees.id, "note": "n" * 256}],
        [{**line, "category_id": fees.id, "planned": True}],
    ]
    for lines in bad:
        resp = client.put(f"/api/v1/budgets/{bid}/lines", json={"lines": lines})
        assert resp.status_code == 400, lines
    ok = client.patch(f"/api/v1/budgets/{bid}", json={"notes": "  Plan  "})
    assert ok.get_json()["notes"] == "Plan"
    cleared = client.patch(f"/api/v1/budgets/{bid}", json={"notes": ""})
    assert cleared.get_json()["notes"] is None


def test_approved_budget_is_locked_and_copy(client, auth_headers, cats):
    bid = _create(client, cats).get_json()["id"]
    assert (
        client.patch(f"/api/v1/budgets/{bid}", json={"approved": True}).get_json()[
            "approved"
        ]
        is True
    )
    assert (
        client.put(f"/api/v1/budgets/{bid}/lines", json={"lines": []}).status_code
        == 409
    )
    assert client.delete(f"/api/v1/budgets/{bid}").status_code == 409

    copy = client.post(f"/api/v1/budgets/{bid}/copy", json={})
    assert copy.status_code == 201
    body = copy.get_json()
    assert body["year"] == 2027 and body["approved"] is False
    assert len(body["lines"]) == 2

    # Unapprove, then edit works again.
    client.patch(f"/api/v1/budgets/{bid}", json={"approved": False})
    assert (
        client.put(f"/api/v1/budgets/{bid}/lines", json={"lines": []}).status_code
        == 200
    )
    assert client.delete(f"/api/v1/budgets/{bid}").status_code == 204


def test_budgets_need_finance(client, auth_headers, cats):
    set_modules(False, "finance.budgets")
    assert client.get("/api/v1/budgets/").status_code == 403


def test_budget_owner_plans_their_budget(client, db, seeded_db, auth_headers, cats):
    from tests.authz.conftest import _create_member_with_role, _login_member

    fees, _ = cats
    lead, _ = _create_member_with_role(
        "lead@test.ch",
        "Teamleitung",
        seeded_db["tier"].id,
        permission_keys=["budgets.budgets.read"],
    )
    own = _create(client, cats).get_json()["id"]
    other = client.post("/api/v1/budgets/", json={"name": "Other", "year": 2026})
    other = other.get_json()["id"]
    resp = client.patch(f"/api/v1/budgets/{own}", json={"owner_id": lead.id})
    assert resp.get_json()["ownerId"] == lead.id
    assert resp.get_json()["ownerName"]
    bad = client.patch(f"/api/v1/budgets/{own}", json={"owner_id": 99999})
    assert bad.status_code == 400

    _login_member(client, "lead@test.ch")
    lines = [{"category_id": fees.id, "kind": "income", "planned": 700}]
    assert client.put(f"/api/v1/budgets/{own}/lines", json={"lines": lines}).status_code == 200
    assert client.patch(f"/api/v1/budgets/{own}", json={"notes": "Plan"}).status_code == 200
    # Not the rest: approving, renaming, handing it on, deleting, other budgets.
    for change in ({"approved": True}, {"name": "Mine"}, {"owner_id": None}):
        assert client.patch(f"/api/v1/budgets/{own}", json=change).status_code == 403
    assert client.delete(f"/api/v1/budgets/{own}").status_code == 403
    assert client.put(f"/api/v1/budgets/{other}/lines", json={"lines": lines}).status_code == 403
    assert client.post("/api/v1/budgets/", json={"name": "New", "year": 2026}).status_code == 403

    # Copying to next year keeps the owner.
    _login_member(client, "admin@test.ch")
    copy = client.post(f"/api/v1/budgets/{own}/copy", json={}).get_json()
    assert copy["ownerId"] == lead.id
