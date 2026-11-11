"""Tables of Finances: the books use Hubra's; Budgets and the closed years'
reports are the plugin's own."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

from .budgets.models import Budget, BudgetLine  # noqa: F401


class YearReport(db.Model):
    """The annual accounts of a closed fiscal year, as they were when it was
    closed. Later changes to categories, accounts or their mapping don't
    change a closed year; reopening it drops the report."""

    __tablename__ = "finance_year_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    report: Mapped[dict] = mapped_column(db.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
