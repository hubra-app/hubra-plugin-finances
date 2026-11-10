"""Dashboard widgets: money today and budget use (docs/dashboards.md in
hubra-app/hubra)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from hubra.core.models.finance import Transaction, TransactionCategory
from tests.authz.conftest import plain_member_token  # noqa: F401
from tests.helpers import set_modules

URL = "/api/v1/app/dashboards/widgets"


def _tx(db, day, amount, method="IBAN", category=None, status="Completed"):
    db.session.add(
        Transaction(
            date=day,
            description="x",
            amount=Decimal(amount),
            type="income" if Decimal(amount) > 0 else "expense",
            method=method,
            status=status,
            category_id=category.id if category else None,
        )
    )


def test_money_today_counts_bank_and_cash(client, db, seeded_db, auth_headers):
    today = date.today()
    _tx(db, date(today.year - 2, 6, 1), "500")  # before the year: opening
    _tx(db, today, "300")
    _tx(db, today, "-120")
    _tx(db, today, "40", method="Cash")
    _tx(db, today, "999", status="Pending")  # not counted
    db.session.commit()
    resp = client.post(f"{URL}/finance.books.cash/data", json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["value"] == "CHF 720.00"
    assert "Bank CHF 680.00" in data["sub"]
    assert "CHF 40.00" in data["sub"]


def test_budget_use_lists_lines_most_used_first(client, db, seeded_db, auth_headers):
    set_modules(True, "finance.budgets")
    year = date.today().year
    hall = TransactionCategory(name="Hall rent")
    drinks = TransactionCategory(name="Drinks")
    db.session.add_all([hall, drinks])
    db.session.commit()
    resp = client.post(
        "/api/v1/budgets/",
        json={
            "name": "Club",
            "year": year,
            "lines": [
                {"category_id": hall.id, "kind": "expense", "planned": 1000},
                {"category_id": drinks.id, "kind": "expense", "planned": 200},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.get_json()
    _tx(db, date(year, 1, 1), "-300", category=hall)
    _tx(db, date(year, 1, 1), "-150", category=drinks)
    db.session.commit()
    resp = client.post(
        f"{URL}/finance.budgets.usage/data", json={"config": {}}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()
    items = resp.get_json()["data"]["items"]
    assert [i["label"] for i in items] == ["Drinks", "Hall rent"]
    assert items[0]["sub"].endswith("75%")


def test_members_without_the_right_get_no_money_widget(client, plain_member_token):  # noqa: F811
    names = {
        w["name"]
        for w in client.get(URL, headers=plain_member_token).get_json()["items"]
    }
    assert "finance.books.cash" not in names
    resp = client.post(
        f"{URL}/finance.books.cash/data", json={}, headers=plain_member_token
    )
    assert resp.status_code == 403
