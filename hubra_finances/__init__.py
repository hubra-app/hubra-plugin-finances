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

Budgets (a plan per year and category, compared with the bookings) was a
plugin of its own up to Budgets 1.3. Finances took it over (``replaces:
[budgets]`` in plugin.yaml) with the same module code, tables, API paths,
permission keys and contract, so clubs keep their budgets, their module
switch and their roles. See budgets/.
"""

from hubra.core.contracts import query_contract
from hubra.core.modules import Blueprint, Module, Schedule

DAY = 24 * 60 * 60.0

books = Module(
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

budgets = Module(
    code="finance.budgets",
    name="Budgets",
    description="Yearly budgets per category, with actuals from transactions",
    default_enabled=False,
    depends_on=("finance",),
    blueprints=(
        Blueprint(
            "hubra_finances.budgets.routes",
            "budgets_bp",
            "/api/v1/budgets",
        ),
    ),
    tables=("budgets", "budget_lines"),
    # Hubra's fee basis (Finanzen › Beitragsgrundlage) asks the approved
    # budget as its "budget" source; the billing year comes from Finance.
    provides=(
        query_contract(
            "finance.budgets.fee_basis.budget",
            "hubra_finances.budgets.fee_basis:budget_source",
            input="hubra_finances.budgets.fee_basis:SourceIn",
            output="hubra_finances.budgets.fee_basis:SourceOut",
            description="The approved budget's expenses of a billing year",
        ),
    ),
    consumes={"finance.billing_period": ">=1,<2"},
)

modules = (books, budgets)
