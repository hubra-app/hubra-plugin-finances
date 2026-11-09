"""The approved budget as the source of the yearly expenses."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra_finances.budgets.fee_basis import budget_lines
from hubra_finances.budgets.models import Budget, BudgetLine
from hubra.core.models.finance import TransactionCategory

fee_basis = pytest.importorskip("hubra.api.finance.fee_basis")


@pytest.fixture
def budgets(db, seeded_db):
    hall = TransactionCategory(name="Hall rent", color="#e8590c")
    events = TransactionCategory(name="Events")
    fees = TransactionCategory(name="Fees")
    db.session.add_all([hall, events, fees])
    db.session.flush()
    club = Budget(year=2026, name="Club", approved=True)
    youth = Budget(year=2026, name="Youth", approved=True)
    draft = Budget(year=2027, name="Club", approved=False)
    db.session.add_all([club, youth, draft])
    db.session.flush()
    db.session.add_all(
        [
            BudgetLine(
                budget_id=club.id,
                category_id=hall.id,
                kind="expense",
                planned=Decimal("9600"),
            ),
            BudgetLine(
                budget_id=club.id,
                category_id=events.id,
                kind="expense",
                planned=Decimal("1500"),
                note="Summer party",
            ),
            BudgetLine(
                budget_id=club.id,
                category_id=fees.id,
                kind="income",
                planned=Decimal("12000"),
            ),
            BudgetLine(
                budget_id=youth.id,
                category_id=events.id,
                kind="expense",
                planned=Decimal("500"),
            ),
            BudgetLine(
                budget_id=draft.id,
                category_id=hall.id,
                kind="expense",
                planned=Decimal("9900"),
            ),
        ]
    )
    db.session.commit()


def test_expense_lines_of_the_approved_budgets(app, db, budgets):
    lines = budget_lines(2026)
    assert [(line["name"], line["amount"]) for line in lines] == [
        ("Hall rent", Decimal("9600")),
        ("Events", Decimal("2000")),
    ]
    assert [item["description"] for item in lines[1]["items"]] == [
        "Summer party",
        "Youth",
    ]


def test_no_approved_budget(app, db, budgets):
    assert budget_lines(2027) is None
    assert budget_lines(2025) is None


def test_offered_as_the_fee_basis_source(app, db, budgets):
    config = {"fee_basis_source": "budget", "fee_basis_extra": 400}
    with (
        patch("hubra.core.modules.get_config", return_value=config),
        patch("hubra.core.modules.is_enabled", return_value=True),
    ):
        basis = fee_basis.fee_basis(today=date(2026, 10, 31))
    assert "budget" in basis["sources"]
    assert basis["period"] == {"year": 2026}
    assert basis["total"] == 9600 + 2000 + 400


def test_a_year_without_an_approved_budget_says_so(app, db, budgets):
    config = {"fee_basis_source": "budget"}
    with (
        patch("hubra.core.modules.get_config", return_value=config),
        patch("hubra.core.modules.is_enabled", return_value=True),
    ):
        basis = fee_basis.fee_basis(today=date(2027, 3, 1))
    assert basis["note"] == "NO_BUDGET"
    assert basis["period"] == {"year": 2027}
