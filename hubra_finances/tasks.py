"""Scheduled bookkeeping: due recurring bookings every day, and the monthly
account statement on the first of the month."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from hubra.core.extensions import db
from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)

MODULE = "finance.books"


@celery_app.task(name="hubra_finances.tasks.book_recurring")
@per_tenant_job(MODULE)
def book_recurring() -> dict:
    """Book the due recurring transactions."""
    from hubra_finances.recurring import book_due

    booked = book_due()
    db.session.commit()
    logger.info("recurring_transactions_booked count=%s", booked)
    return {"booked": booked}


@celery_app.task(name="hubra_finances.tasks.send_statements")
@per_tenant_job(MODULE)
def send_statements(today: date | None = None) -> dict:
    """On the first of the month, mail last month's account statement to the
    address in the finance settings, if the club asked for one. Runs daily,
    so exactly one run falls on the first."""
    from hubra_finances.statement import send_statement, statement_settings

    today = today or date.today()
    if today.day != 1:
        return {"sent": 0}
    settings = statement_settings()
    if not settings["enabled"]:
        return {"sent": 0}
    last_month = (today - timedelta(days=1)).replace(day=1)
    send_statement(last_month, settings["email"])
    db.session.commit()
    return {"sent": 1}


@celery_app.task(name="hubra_finances.tasks.purge_orphans")
@per_tenant_job(MODULE)
def purge_orphans() -> dict:
    """Clear budget owners who were deleted and lines of deleted categories
    (see budgets.services.purge_orphans)."""
    from hubra_finances.budgets.services import purge_orphans as purge

    result = purge()
    db.session.commit()
    if result["owners"] or result["lines"]:
        logger.info(
            "finances_orphans_purged owners=%s lines=%s",
            result["owners"],
            result["lines"],
        )
    return result
