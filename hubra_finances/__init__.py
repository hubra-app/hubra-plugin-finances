"""Finances: the club's books next to Hubra's invoices.

Transactions, categories, the overview, recurring bookings, the monthly
account statement and the annual accounts were built into Hubra's Finance
module up to 0.x. Invoices, reminders, the QR-bill, fees and external
parties stay in Hubra. The tables, the API paths (/api/v1/app/finance/...)
and the permission keys (finance.transactions.*, finance.overview.read, ...)
stay the same, so clubs keep their books and their roles.

Paying an invoice books its income here: Hubra announces invoice.created,
invoice.updated and invoice.deleted, and bookings.py keeps the linked
transaction in step, inside the same database transaction.
"""

from hubra.core.contracts import query_contract
from hubra.core.modules import Blueprint, Module, Schedule

DAY = 24 * 60 * 60.0

module = Module(
    code="finance.books",
    name="Finances",
    description="Transactions, categories, overview, recurring bookings, statements and annual accounts",
    default_enabled=True,
    depends_on=("finance",),
    blueprints=(
        Blueprint(
            "hubra_finances.routes",
            "books_bp",
            "/api/v1/app/finance",
            perm_prefix="finance",
        ),
    ),
    events={
        "invoice.created": "hubra_finances.bookings:on_invoice_created",
        "invoice.updated": "hubra_finances.bookings:on_invoice_updated",
        "invoice.deleted": "hubra_finances.bookings:on_invoice_deleted",
    },
    # An invoice and its booking are saved together.
    events_in_transaction=("invoice.created", "invoice.updated", "invoice.deleted"),
    # Hubra's fee basis asks these; Finance answers the billing year and
    # marks invoices paid when their income is booked (docs/contracts.md).
    provides=(
        query_contract(
            "finance.books.fee_basis.recurring",
            "hubra_finances.fee_basis:recurring_source",
            input="hubra_finances.fee_basis:SourceIn",
            output="hubra_finances.fee_basis:SourceOut",
            description="Recurring expenses that count for fees, per year",
        ),
        query_contract(
            "finance.books.fee_basis.last_year",
            "hubra_finances.fee_basis:last_year_source",
            input="hubra_finances.fee_basis:SourceIn",
            output="hubra_finances.fee_basis:SourceOut",
            description="Confirmed expenses of the last full billing year",
        ),
    ),
    consumes={
        "finance.billing_period": ">=1,<2",
        "finance.invoice.set_status": ">=1,<2",
    },
    tasks=("hubra_finances.tasks",),
    schedule=(
        Schedule("finances-book-recurring", "hubra_finances.tasks.book_recurring", DAY),
        Schedule("finances-statements", "hubra_finances.tasks.send_statements", DAY),
    ),
)
