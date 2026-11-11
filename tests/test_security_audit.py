"""Findings of the 2026-11 security review: changes to the books leave an
audit trail, column limits are a 400 (not a database error), and an approved
budget can't lose a line through its category."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from hubra.core.models.audit import AuditEntry
from hubra.core.models.finance import TransactionCategory

URL = "/api/v1/finance"


def _actions(db) -> list[str]:
    return list(db.session.scalars(select(AuditEntry.action)))


@pytest.fixture
def category(db, seeded_db):
    cat = TransactionCategory(name="Hall", color="#123456")
    db.session.add(cat)
    db.session.commit()
    return cat


def test_category_changes_are_audited(client, auth_headers, db, seeded_db):
    created = client.post(
        f"{URL}/transaction-categories", json={"name": "Kiosk", "color": "#112233"}
    )
    assert created.status_code == 201
    cid = created.get_json()["id"]
    assert client.patch(
        f"{URL}/transaction-categories/{cid}", json={"name": "Kiosk 2"}
    ).status_code == 200
    assert client.delete(f"{URL}/transaction-categories/{cid}").status_code == 204
    actions = _actions(db)
    for action in (
        "create_transaction_category",
        "update_transaction_category",
        "delete_transaction_category",
    ):
        assert action in actions


def test_account_rename_and_mapping_are_audited(client, auth_headers, db, category):
    chart = client.get(f"{URL}/accounts").get_json()
    rent = next(a for a in chart["accounts"] if a["number"] == "6000")
    assert client.patch(
        f"{URL}/accounts/{rent['id']}", json={"name": "Miete"}
    ).status_code == 200
    assert client.put(
        f"{URL}/accounts/categories/{category.id}", json={"accountId": rent["id"]}
    ).status_code == 200
    actions = _actions(db)
    assert "rename_account" in actions
    assert "map_category_account" in actions


def _tx(category_id, **extra):
    body = {
        "date": date.today().isoformat(),
        "description": "x",
        "category_id": category_id,
        "amount": 10.0,
        "method": "IBAN",
        "type": "expense",
    }
    body.update(extra)
    return body


def test_amount_and_payee_limits(client, auth_headers, category):
    for extra in ({"amount": 1e10}, {"amount": 1e300}, {"payee_name": "p" * 256}):
        resp = client.post(f"{URL}/transactions", json=_tx(category.id, **extra))
        assert resp.status_code == 400, extra
    ok = client.post(
        f"{URL}/transactions", json=_tx(category.id, amount=9_999_999_999.99)
    )
    assert ok.status_code == 201
    tid = ok.get_json()["id"]
    for change in ({"amount": 1e10}, {"payee_name": "p" * 256}):
        resp = client.patch(f"{URL}/transactions/{tid}", json=change)
        assert resp.status_code == 400, change


def test_statement_month_out_of_range(client, auth_headers, seeded_db):
    for month in ("9999-12", "0001-01", "2026-13", "x"):
        resp = client.get(f"{URL}/statement.pdf?month={month}")
        assert resp.status_code == 400, month


def test_category_of_an_approved_budget_stays(client, auth_headers, db, category):
    budget = client.post(
        "/api/v1/budgets/",
        json={
            "name": "Club",
            "year": 2026,
            "lines": [{"category_id": category.id, "kind": "expense", "planned": 100}],
        },
    )
    assert budget.status_code == 201, budget.get_json()
    bid = budget.get_json()["id"]
    assert client.patch(
        f"/api/v1/budgets/{bid}", json={"approved": "false"}
    ).status_code == 400
    assert client.patch(f"/api/v1/budgets/{bid}", json={"approved": True}).status_code == 200
    resp = client.delete(f"{URL}/transaction-categories/{category.id}")
    assert resp.status_code == 409
    lines = client.get(f"/api/v1/budgets/{bid}").get_json()["lines"]
    assert len(lines) == 1
