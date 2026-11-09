"""The approved budget as the source of the yearly expenses that percentage
and formula tiers share (Finanzen › Beitragsgrundlage in Hubra).

Hubra asks it through the query contract ``finance.budgets.fee_basis.budget``
(docs/contracts.md in hubra); no Hubra internals are imported."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select

from hubra.core.contracts import SYSTEM, query
from hubra.core.extensions import db

from .models import Budget


def budget_lines(year: int) -> list[dict] | None:
    """The expense lines of the year's approved budgets, one per category;
    None when no budget of that year is approved."""
    budgets = db.session.scalars(
        select(Budget).where(Budget.year == year).where(Budget.approved.is_(True))
    ).all()
    if not budgets:
        return None
    lines: dict[int, dict] = {}
    for budget in budgets:
        for line in budget.lines:
            if line.kind != "expense":
                continue
            entry = lines.setdefault(
                line.category_id,
                {
                    "category_id": line.category_id,
                    "name": line.category.name if line.category else None,
                    "color": line.category.color if line.category else None,
                    "amount": Decimal(0),
                    "items": [],
                },
            )
            entry["amount"] += Decimal(line.planned)
            entry["items"].append(
                {"description": line.note or budget.name, "amount": float(line.planned)}
            )
    return sorted(lines.values(), key=lambda line: -line["amount"])


class SourceIn(BaseModel):
    on: date


class Line(BaseModel):
    category_id: int | None = None
    name: str | None = None
    color: str | None = None
    amount: float
    items: list[dict] = []


class SourceOut(BaseModel):
    lines: list[Line]
    period: dict | None = None
    note: str | None = None


def budget_source(ctx, data: SourceIn) -> SourceOut:
    """The ``finance.budgets.fee_basis.budget`` query Hubra's fee basis asks:
    the budget of the billing year that *on* falls in."""
    period = query("finance.billing_period", on=data.on, actor=SYSTEM)
    year = date.fromisoformat(period["start"]).year
    lines = budget_lines(year)
    if lines is None:
        return SourceOut(lines=[], period={"year": year}, note="NO_BUDGET")
    return SourceOut(lines=lines, period={"year": year})
