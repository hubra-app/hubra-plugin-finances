"""Dashboard widgets of Finances (docs/dashboards.md in hubra-app/hubra).

finance.books.cash     stat  money on the bank and cash accounts today
finance.budgets.usage  list  this year's budget lines: booked against planned,
                             the most used first (Budgets had it up to 1.3)

They read as the viewing member; the contract's ``perm`` decides who may
add them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from hubra.core.extensions import db

from .annual import BANK, CASH, _money_moves, opening_balances, year_bounds

_ZERO = Decimal("0")


def _chf(amount, places: int = 2) -> str:
    return f"CHF {Decimal(amount or 0):,.{places}f}".replace(",", "'")


def _german(member) -> bool:
    return (getattr(member, "language", None) or "de").lower().startswith("de")


def cash(ctx, config: dict) -> dict:
    """Bank and cash today: the fiscal year's opening balances plus the
    completed bookings since then (as the annual accounts count them)."""
    today = date.today()
    start, _end = year_bounds(today.year)
    if start > today:
        start, _end = year_bounds(today.year - 1)
    opening, _source = opening_balances(start)
    moves = _money_moves(start, today)
    bank = opening.get(BANK, _ZERO) + moves.get(BANK, _ZERO)
    cash_box = opening.get(CASH, _ZERO) + moves.get(CASH, _ZERO)
    words = ("Bank", "Kasse") if _german(ctx.actor) else ("Bank", "Cash")
    return {
        "value": _chf(bank + cash_box),
        "sub": f"{words[0]} {_chf(bank)} · {words[1]} {_chf(cash_box)}",
        "path": "/app/finance/overview",
    }


def usage(ctx, config: dict) -> dict:
    """Lines of this year's budget (the approved one first), most used first."""
    from .budgets.models import Budget
    from .budgets.services import actuals

    try:
        count = max(1, min(int(config.get("count") or 5), 20))
    except (TypeError, ValueError):
        count = 5
    kind = "income" if config.get("income") else "expense"
    year = date.today().year
    budget = db.session.scalar(
        select(Budget)
        .where(Budget.year == year)
        .order_by(Budget.approved.desc(), Budget.updated_at.desc(), Budget.id.desc())
        .limit(1)
    )
    if budget is None:
        return {"items": [], "total": 0}
    booked = actuals(year)
    rows = []
    for line in budget.lines:
        if line.kind != kind:
            continue
        # Expenses are booked negative; the budget plans them positive.
        actual = abs(booked.get((line.category_id, line.kind), _ZERO))
        share = int(actual * 100 / line.planned) if line.planned else 0
        rows.append((share, line, actual))
    rows.sort(key=lambda r: (-r[0], r[1].id))
    items = [
        {
            "label": line.category.name if line.category else "–",
            "sub": f"{_chf(actual, 0)} / {_chf(line.planned, 0)} · {share}%",
            "path": "/app/finance/budgets",
        }
        for share, line, actual in rows[:count]
    ]
    return {"items": items, "total": len(rows)}
