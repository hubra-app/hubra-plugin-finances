"""Bookkeeping services: transaction categories, transactions, the overview
and the summary by category. Moved out of Hubra's Finance module;
invoices stay in Hubra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import selectinload

from hubra.core.contracts import SYSTEM, call
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
from hubra.core.models.member import Member
from hubra.core.utils import escape_like, log_audit


def _parse_page_params(args):
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(args.get("pageSize", 25))))
    except (TypeError, ValueError):
        page_size = 25
    return page, page_size


def _paginate(query, page, page_size, schema):
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    items = db.session.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "data": schema.dump(items),
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
    }


class TransactionCategoryService:
    """Operations on a single transaction category."""

    @staticmethod
    def get(id: int) -> TransactionCategory:
        """Return a category or raise 404."""
        category = db.session.get(TransactionCategory, id)
        if category is None:
            raise_error(404, "NOT_FOUND", f"TransactionCategory {id} not found")
        return category  # type: ignore[return-value]

    @staticmethod
    def update(category: TransactionCategory, data: dict) -> TransactionCategory:
        """Update name/color on a category."""
        if "name" in data and data["name"] != category.name:
            conflict = db.session.scalar(
                select(TransactionCategory.id)
                .where(TransactionCategory.name == data["name"])
                .where(TransactionCategory.id != category.id)
            )
            if conflict is not None:
                raise_error(
                    409, "CONFLICT", f"Category name '{data['name']}' already exists"
                )
            category.name = data["name"]
        if "color" in data:
            category.color = data["color"]
        return category

    @staticmethod
    def delete(category_id: int) -> None:
        """Delete a category if not default and no transactions reference it."""
        category = TransactionCategoryService.get(category_id)

        if category.is_default:
            raise_error(409, "CONFLICT", "Cannot delete a default category")

        has_transactions = db.session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.category_id == category.id
            )
        )
        if has_transactions:
            raise_error(
                409, "CONFLICT", "Category is referenced by existing transactions"
            )

        # Budget lines go with their category (ON DELETE CASCADE), and an
        # approved budget must not change, so its categories stay.
        from hubra_finances.budgets.models import Budget, BudgetLine

        in_approved = db.session.scalar(
            select(func.count(BudgetLine.id))
            .join(Budget, BudgetLine.budget_id == Budget.id)
            .where(BudgetLine.category_id == category.id)
            .where(Budget.approved.is_(True))
        )
        if in_approved:
            raise_error(
                409, "CONFLICT", "Category is planned in an approved budget"
            )
        # Club schemas are cloned without foreign keys, so the cascade may not
        # run there: the open budgets' lines of this category go explicitly.
        db.session.execute(
            delete(BudgetLine).where(BudgetLine.category_id == category.id)
        )

        db.session.delete(category)


class TransactionCategoriesService:
    """Operations on the transaction category collection."""

    @staticmethod
    def list() -> list[TransactionCategory]:
        return db.session.scalars(  # type: ignore[return-value]
            select(TransactionCategory).order_by(TransactionCategory.name)
        ).all()

    @staticmethod
    def create(data: dict) -> TransactionCategory:
        """Create a new transaction category."""
        existing = db.session.scalar(
            select(TransactionCategory.id).where(
                TransactionCategory.name == data["name"]
            )
        )
        if existing is not None:
            raise_error(
                409, "CONFLICT", f"Category name '{data['name']}' already exists"
            )

        category = TransactionCategory(
            name=data["name"],
            color=data.get("color"),
        )
        # Once the club has a chart of accounts, a new category starts on
        # the account its name suggests (the board can change it).
        from hubra_finances.annual import guess_account
        from hubra.core.models.finance import Account

        number = guess_account(category.name)
        if number:
            category.account_id = db.session.scalar(
                select(Account.id).where(Account.number == number)
            )
        db.session.add(category)
        db.session.flush()

        db.session.refresh(category)
        return category  # type: ignore[return-value]


class TransactionService:
    """Operations on a single transaction."""

    @staticmethod
    def get(id: int) -> Transaction:
        """Return a transaction or raise 404."""
        transaction = db.session.get(Transaction, id)
        if transaction is None:
            raise_error(404, "NOT_FOUND", f"Transaction {id} not found")
        return transaction  # type: ignore[return-value]

    @staticmethod
    def update(transaction: Transaction, data: dict, actor_id: int) -> Transaction:
        """Update allowed fields on a transaction."""
        if data.get("category_id") is not None:
            category = db.session.get(TransactionCategory, data["category_id"])
            if category is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"Transaction category {data['category_id']} not found",
                )

        if "member_id" in data and data["member_id"] is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == data["member_id"])
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"Member {data['member_id']} not found or archived",
                )

        for field in (
            "status",
            "description",
            "date",
            "amount",
            "method",
            "type",
            "category_id",
            "member_id",
            "payee_name",
        ):
            if field in data:
                setattr(transaction, field, data[field])

        # The API takes amounts as positive numbers and stores expenses
        # negative (as create does); keep that when amount or type change.
        if "amount" in data or "type" in data:
            amount = abs(Decimal(str(transaction.amount)))
            transaction.amount = -amount if transaction.type == "expense" else amount

        # Booking an invoice's income as received pays the invoice, so no
        # reminder goes to someone who paid (and the other way round).
        if "status" in data:
            invoice = db.session.scalar(
                select(Invoice).where(Invoice.transaction_id == transaction.id)
            )
            # As SYSTEM: the right to book the income is enough here.
            status = None
            if invoice is not None:
                if transaction.status == "Completed" and invoice.status != "Paid":
                    status = "Paid"
                elif transaction.status == "Pending" and invoice.status == "Paid":
                    status = "Open"
            if status is not None:
                call(
                    "finance.invoice.set_status",
                    invoice_id=invoice.id,
                    status=status,
                    actor_id=actor_id,
                    actor=SYSTEM,
                )

        log_audit(
            actor_id=actor_id,
            action="update_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=transaction.description,
        )
        return transaction

    @staticmethod
    def delete(transaction_id: int, actor_id: int) -> None:
        """Delete a transaction. An invoice it was the income of stays, with
        its status and send history; it is only unlinked."""
        transaction = TransactionService.get(transaction_id)

        log_audit(
            actor_id=actor_id,
            action="delete_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=transaction.description,
        )

        linked_invoice = db.session.scalar(
            select(Invoice).where(Invoice.transaction_id == transaction.id)
        )
        if linked_invoice is not None:
            linked_invoice.transaction_id = None
            db.session.flush()

        db.session.delete(transaction)


class TransactionsService:
    """Operations on the transaction collection."""

    @staticmethod
    def list(args, schema) -> dict:
        """List transactions with filtering and pagination."""
        page, page_size = _parse_page_params(args)

        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.category),
                selectinload(Transaction.member).selectinload(Member.user),
                selectinload(Transaction.invoice),
            )
            .order_by(Transaction.date.desc(), Transaction.id.desc())
        )

        search = args.get("search", "").strip()
        if search:
            query = query.where(
                Transaction.description.ilike(f"%{escape_like(search)}%", escape="\\")
            )

        tx_type = args.get("type", "").strip()
        if tx_type:
            query = query.where(Transaction.type == tx_type)

        category_name = args.get("category", "").strip()
        if category_name:
            query = query.join(
                TransactionCategory,
                Transaction.category_id == TransactionCategory.id,
            ).where(TransactionCategory.name == category_name)

        from_date = args.get("from", "").strip()
        if from_date:
            try:
                query = query.where(Transaction.date >= date.fromisoformat(from_date))
            except ValueError:
                pass

        to_date = args.get("to", "").strip()
        if to_date:
            try:
                query = query.where(Transaction.date <= date.fromisoformat(to_date))
            except ValueError:
                pass

        return _paginate(query, page, page_size, schema)  # schema injected by route

    @staticmethod
    def create(data: dict, actor_id: int) -> Transaction:
        """Create a new transaction."""
        member_id = data.get("member_id")
        if member_id is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == member_id)
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404, "NOT_FOUND", f"Member {member_id} not found or archived"
                )

        category_id = data.get("category_id")
        if category_id is not None and not db.session.get(
            TransactionCategory, category_id
        ):
            raise_error(
                404, "NOT_FOUND", f"Transaction category {category_id} not found"
            )

        amount = data["amount"]
        if data["type"] == "expense":
            amount = -abs(amount)

        transaction = Transaction(
            date=data["date"],
            description=data["description"],
            category_id=category_id,
            member_id=member_id,
            payee_name=data.get("payee_name"),
            amount=amount,
            method=data["method"],
            type=data["type"],
        )
        db.session.add(transaction)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=data["description"],
        )

        db.session.refresh(transaction)
        return transaction  # type: ignore[return-value]


class FinanceOverviewService:
    """Aggregated finance overview."""

    @staticmethod
    def get() -> dict:
        """Return balance, MTD figures, 12-month history, and open invoice stats."""
        today = date.today()
        current_year = today.year
        current_month = today.month

        balance = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.status == "Completed"
                )
            )
            or 0
        )

        mtd_income = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.status == "Completed")
                .where(func.extract("year", Transaction.date) == current_year)
                .where(func.extract("month", Transaction.date) == current_month)
                .where(Transaction.amount > 0)
            )
            or 0
        )

        mtd_expense_raw = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.status == "Completed")
                .where(func.extract("year", Transaction.date) == current_year)
                .where(func.extract("month", Transaction.date) == current_month)
                .where(Transaction.amount < 0)
            )
            or 0
        )

        income_mtd = float(mtd_income)
        expenses_mtd = abs(float(mtd_expense_raw))
        net_mtd = income_mtd - expenses_mtd

        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        months_data = []
        for i in range(11, -1, -1):
            month_offset = (current_month - 1 - i) % 12 + 1
            year_offset = current_year + ((current_month - 1 - i) // 12)

            inc = (
                db.session.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .where(Transaction.status == "Completed")
                    .where(func.extract("year", Transaction.date) == year_offset)
                    .where(func.extract("month", Transaction.date) == month_offset)
                    .where(Transaction.amount > 0)
                )
                or 0
            )

            exp = (
                db.session.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .where(Transaction.status == "Completed")
                    .where(func.extract("year", Transaction.date) == year_offset)
                    .where(func.extract("month", Transaction.date) == month_offset)
                    .where(Transaction.amount < 0)
                )
                or 0
            )

            months_data.append(
                {
                    "m": month_names[month_offset - 1],
                    "year": int(year_offset),
                    "month": int(month_offset),
                    "inc": round(float(inc) / 1000, 2),
                    "exp": round(abs(float(exp)) / 1000, 2),
                }
            )

        open_stats = db.session.execute(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.amount), 0),
            ).where(Invoice.status != "Paid")
        ).one()
        open_count = open_stats[0] or 0
        open_amount = open_stats[1] or 0

        return {
            "balance": float(balance),
            "incomeMTD": income_mtd,
            "expensesMTD": expenses_mtd,
            "netMTD": net_mtd,
            "months": months_data,
            "openInvoices": {
                "count": open_count,
                "amount": float(open_amount),
            },
        }


def _summary_range(args) -> tuple[date, date]:
    """The from/to dates of a summary; the current calendar year by default."""
    today = date.today()
    try:
        start = date.fromisoformat(args.get("from") or f"{today.year}-01-01")
        end = date.fromisoformat(args.get("to") or f"{start.year}-12-31")
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "from and to must be ISO dates")
    if end < start:
        raise_error(400, "VALIDATION_ERROR", "to is before from")
    if (end - start).days > 366 * 5:
        raise_error(400, "VALIDATION_ERROR", "The range can be at most 5 years")
    return start, end


class FinanceSummaryService:
    """Income and expenses per category over a date range."""

    @staticmethod
    def get(args) -> dict:
        start, end = _summary_range(args)
        income = func.coalesce(
            func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)),
            0,
        )
        expense = func.coalesce(
            func.sum(case((Transaction.amount < 0, Transaction.amount), else_=0)),
            0,
        )
        rows = db.session.execute(
            select(Transaction.category_id, income, expense, func.count(Transaction.id))
            .where(Transaction.status == "Completed")
            .where(Transaction.date >= start)
            .where(Transaction.date <= end)
            .group_by(Transaction.category_id)
        ).all()
        names = {c.id: c for c in db.session.scalars(select(TransactionCategory)).all()}

        categories = []
        total_income = Decimal(0)
        total_expense = Decimal(0)
        for category_id, inc, exp, count in rows:
            inc = Decimal(str(inc))
            exp = abs(Decimal(str(exp)))
            total_income += inc
            total_expense += exp
            category = names.get(category_id)
            categories.append(
                {
                    "id": category_id,
                    "name": category.name if category else None,
                    "color": category.color if category else None,
                    "income": float(inc),
                    "expense": float(exp),
                    "net": float(inc - exp),
                    "count": count,
                }
            )
        # Biggest movements first; uncategorised last among equals.
        categories.sort(key=lambda c: (-(c["income"] + c["expense"]), c["id"] is None))
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "income": float(total_income),
            "expense": float(total_expense),
            "net": float(total_income - total_expense),
            "categories": categories,
        }

