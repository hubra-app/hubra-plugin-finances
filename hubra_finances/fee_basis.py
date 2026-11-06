"""The fee basis sources that come from the books: ``recurring`` (the
recurring expenses marked as counting for fees, times their payments per
year) and ``last_year`` (the confirmed expenses of the last full billing
year). Hubra keeps the fee basis itself (Finanzen › Beitragsgrundlage) and
falls back to the typed-in figure without this plugin."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.finance import RecurringTransaction, Transaction, TransactionCategory


def _fb():
    from hubra.api.finance import fee_basis

    return fee_basis


def _lines_by_category(rows) -> list[dict]:
    """(category, item, amount) rows as one line per category, largest first."""
    lines: dict[int | None, dict] = {}
    for category, item, amount in rows:
        key = category.id if category is not None else None
        line = lines.setdefault(
            key,
            {
                "category_id": key,
                "name": category.name if category is not None else None,
                "color": category.color if category is not None else None,
                "amount": Decimal(0),
                "items": [],
            },
        )
        line["amount"] += amount
        if item is not None:
            line["items"].append(item)
    return sorted(lines.values(), key=lambda line: -line["amount"])


def recurring_lines() -> list[dict]:
    from hubra_finances.recurring import yearly_amount

    rules = db.session.scalars(
        select(RecurringTransaction)
        .where(RecurringTransaction.type == "expense")
        .where(RecurringTransaction.active.is_(True))
        .where(RecurringTransaction.counts_for_fees.is_(True))
        .where(RecurringTransaction.next_date.isnot(None))
    ).all()
    rows = []
    for rule in rules:
        amount = yearly_amount(rule)
        rows.append(
            (
                rule.category,
                {
                    "id": rule.id,
                    "description": rule.description,
                    "interval": rule.interval,
                    "amount": float(rule.amount),
                    "yearly": float(amount),
                },
                amount,
            )
        )
    return _lines_by_category(rows)


def last_year_lines(today: date) -> tuple[list[dict], date, date]:
    fb = _fb()
    this_start, _ = fb._billing_year(today)
    start, end = fb._billing_year(this_start - timedelta(days=1))
    rows = db.session.execute(
        select(Transaction.category_id, func.sum(Transaction.amount))
        .where(Transaction.status == "Completed")
        .where(Transaction.amount < 0)
        .where(Transaction.date >= start)
        .where(Transaction.date <= end)
        .group_by(Transaction.category_id)
    ).all()
    categories = {c.id: c for c in db.session.scalars(select(TransactionCategory)).all()}
    lines = _lines_by_category(
        (categories.get(category_id), None, abs(Decimal(str(total))))
        for category_id, total in rows
    )
    return lines, start, end


def _recurring_source(today: date):
    return recurring_lines(), None


def _last_year_source(today: date):
    lines, start, end = last_year_lines(today)
    return lines, {"from": start.isoformat(), "to": end.isoformat()}


def register() -> None:
    fb = _fb()
    fb.register_basis_source("recurring", "finance.books", _recurring_source)
    fb.register_basis_source("last_year", "finance.books", _last_year_source)
