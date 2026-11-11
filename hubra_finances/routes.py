"""Bookkeeping routes, served under Hubra's /api/v1/app/finance next to its
invoices. The blueprint keeps Finance's permission keys
(finance.transactions.read, ...) through perm_prefix in the manifest, so
roles keep their rights."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file
from marshmallow import ValidationError

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import TransactionCategory
from hubra.core.permissions import permission_required
from hubra.core.schemas.finance import (
    TransactionCategoryCreateSchema,
    TransactionCategorySchema,
    TransactionSchema,
)
from hubra.core.utils import log_audit
from hubra_finances import annual  # its import guards closed fiscal years
from hubra_finances.recurring import RecurringTransactionService, recurring_to_dict
from hubra_finances.schemas import TransactionCreateSchema, TransactionUpdateSchema
from hubra_finances.services import (
    FinanceOverviewService,
    FinanceSummaryService,
    TransactionCategoriesService,
    TransactionCategoryService,
    TransactionService,
    TransactionsService,
)

books_bp = Blueprint("books_bp", __name__)

_category_schema = TransactionCategorySchema()
_categories_schema = TransactionCategorySchema(many=True)
_category_create_schema = TransactionCategoryCreateSchema()

_transaction_schema = TransactionSchema()
_transactions_schema = TransactionSchema(many=True)
_transaction_create_schema = TransactionCreateSchema()
_transaction_update_schema = TransactionUpdateSchema()


@books_bp.get("/transaction-categories")
@permission_required("transaction_categories", "read", "View transaction categories")
def list_transaction_categories():
    return jsonify(_categories_schema.dump(TransactionCategoriesService.list())), 200


@books_bp.post("/transaction-categories")
@permission_required(
    "transaction_categories", "create", "Create transaction categories"
)
def create_transaction_category():
    body = request.get_json(silent=True) or {}
    try:
        data = _category_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    category = TransactionCategoriesService.create(data)
    log_audit(
        get_current_member().id,
        "create_transaction_category",
        "TransactionCategory",
        category.id,
        category.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_category_schema.dump(category)), 201


@books_bp.patch("/transaction-categories/<int:id>")
@permission_required(
    "transaction_categories", "update", "Update transaction categories"
)
def update_transaction_category(id: int):
    category = TransactionCategoryService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _category_create_schema.load(body, partial=True)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    TransactionCategoryService.update(category, data)
    log_audit(
        get_current_member().id,
        "update_transaction_category",
        "TransactionCategory",
        category.id,
        category.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(category)
    return jsonify(_category_schema.dump(category)), 200


@books_bp.delete("/transaction-categories/<int:id>")
@permission_required(
    "transaction_categories", "delete", "Delete transaction categories"
)
def delete_transaction_category(id: int):
    name = TransactionCategoryService.get(id).name
    TransactionCategoryService.delete(id)
    log_audit(
        get_current_member().id,
        "delete_transaction_category",
        "TransactionCategory",
        id,
        name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


@books_bp.get("/transactions")
@permission_required("transactions", "read", "View transactions")
def list_transactions():
    return jsonify(TransactionsService.list(request.args, _transactions_schema)), 200


@books_bp.get("/transactions/<int:id>")
@permission_required("transactions", "read", "View transactions")
def get_transaction(id: int):
    return jsonify(_transaction_schema.dump(TransactionService.get(id))), 200


@books_bp.post("/transactions")
@permission_required("transactions", "create", "Create transactions")
def create_transaction():
    body = request.get_json(silent=True) or {}
    try:
        data = _transaction_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    transaction = TransactionsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_transaction_schema.dump(transaction)), 201


@books_bp.patch("/transactions/<int:id>")
@permission_required("transactions", "update", "Update transactions")
def update_transaction(id: int):
    transaction = TransactionService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _transaction_update_schema.load(body, partial=True)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    TransactionService.update(transaction, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(transaction)
    return jsonify(_transaction_schema.dump(transaction)), 200


@books_bp.delete("/transactions/<int:id>")
@permission_required("transactions", "delete", "Delete transactions")
def delete_transaction(id: int):
    TransactionService.delete(id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


@books_bp.get("/overview")
@permission_required("overview", "read", "View finance overview")
def finance_overview():
    return jsonify(FinanceOverviewService.get()), 200


@books_bp.get("/summary")
@permission_required("overview", "read", "View finance overview")
def finance_summary():
    return jsonify(FinanceSummaryService.get(request.args)), 200


@books_bp.get("/recurring")
@permission_required("transactions", "read", "View transactions")
def list_recurring():
    rules = RecurringTransactionService.list()
    return jsonify([recurring_to_dict(r) for r in rules]), 200


@books_bp.post("/recurring")
@permission_required("transactions", "create", "Create transactions")
def create_recurring():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected a JSON object", 400)
    rule = RecurringTransactionService.create(body, get_current_member().id)
    db.session.commit()
    return jsonify(recurring_to_dict(rule)), 201


@books_bp.patch("/recurring/<int:id>")
@permission_required("transactions", "update", "Update transactions")
def update_recurring(id: int):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected a JSON object", 400)
    rule = RecurringTransactionService.update(id, body, get_current_member().id)
    db.session.commit()
    return jsonify(recurring_to_dict(rule)), 200


@books_bp.delete("/recurring/<int:id>")
@permission_required("transactions", "delete", "Delete transactions")
def delete_recurring(id: int):
    RecurringTransactionService.delete(id, get_current_member().id)
    db.session.commit()
    return "", 204


@books_bp.get("/statement.pdf")
@permission_required("overview", "read", "View finance overview")
def download_statement():
    """The account statement of ?month=YYYY-MM (last month by default)."""
    from io import BytesIO

    from hubra_finances.statement import month_of, statement_data, statement_pdf

    start = month_of(request.args.get("month"))
    pdf = statement_pdf(statement_data(start))
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"kontoauszug-{start:%Y-%m}.pdf",
    )


@books_bp.post("/statement/send")
# Mailing is more than reading: the right to book (treasurer), not just to
# see the overview (the board's "view").
@permission_required("transactions", "create", "Create transactions")
def send_statement_now():
    """Mail a month's statement to the club's statement address now."""
    from hubra_finances.statement import month_of, send_statement, statement_settings

    body = request.get_json(silent=True) or {}
    email = statement_settings()["email"]
    if "@" not in email:
        return api_error(
            "STATEMENT_EMAIL_MISSING",
            "Set the address for the account statement first",
            400,
        )
    month = body.get("month") if isinstance(body, dict) else None
    result = send_statement(month_of(month if isinstance(month, str) else None), email)
    db.session.commit()
    return jsonify(result), 202


def _year_arg(year: int) -> int:
    if not 1900 <= year <= 2999:
        raise_error(400, "VALIDATION_ERROR", "Unknown year")
    return year


@books_bp.get("/accounts")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def list_accounts():
    """The chart of accounts and which account each category counts on."""

    data = annual.list_chart()
    db.session.commit()  # the chart is seeded on first read
    return jsonify(data)


@books_bp.post("/accounts")
@permission_required("accounts", "update", "Change the chart of accounts")
def create_account():

    account = annual.create_account(request.get_json(silent=True) or {})
    log_audit(
        get_current_member().id,
        "create_account",
        "Account",
        account.id,
        f"{account.number} {account.name}",
    )
    db.session.commit()
    return jsonify(annual.account_dict(account)), 201


@books_bp.patch("/accounts/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def update_account(id: int):
    from hubra.core.models.finance import Account

    account = db.session.get(Account, id) or raise_error(
        404, "NOT_FOUND", "Account not found"
    )
    annual.update_account(account, request.get_json(silent=True) or {})
    log_audit(
        get_current_member().id,
        "rename_account",
        "Account",
        account.id,
        f"{account.number} {account.name}",
    )
    db.session.commit()
    return jsonify(annual.account_dict(account))


@books_bp.delete("/accounts/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def delete_account(id: int):
    from hubra.core.models.finance import Account

    account = db.session.get(Account, id) or raise_error(
        404, "NOT_FOUND", "Account not found"
    )
    label = f"{account.number} {account.name}"
    annual.delete_account(account)
    log_audit(get_current_member().id, "delete_account", "Account", id, label)
    db.session.commit()
    return "", 204


@books_bp.put("/accounts/categories/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def map_category_account(id: int):
    """``{"accountId": int | null}``: the account a category counts on."""

    category = db.session.get(TransactionCategory, id) or raise_error(
        404, "NOT_FOUND", "Category not found"
    )
    body = request.get_json(silent=True) or {}
    account_id = body.get("accountId")
    if account_id is not None and (
        not isinstance(account_id, int) or isinstance(account_id, bool)
    ):
        raise_error(400, "VALIDATION_ERROR", "accountId must be a number or null")
    annual.map_category(category, account_id)
    log_audit(
        get_current_member().id,
        "map_category_account",
        "TransactionCategory",
        category.id,
        f"{category.name} → {account_id or '-'}",
    )
    db.session.commit()
    return jsonify({"id": category.id, "accountId": category.account_id})


@books_bp.get("/annual")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def list_fiscal_years():

    years = annual.years_overview()
    db.session.commit()
    return jsonify({"years": years, "startMonth": annual.start_month()})


@books_bp.get("/annual/<int:year>")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def get_annual_accounts(year: int):

    report = annual.annual_report(_year_arg(year))
    db.session.commit()
    return jsonify(report)


@books_bp.get("/annual/<int:year>.pdf")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def download_annual_accounts(year: int):
    from io import BytesIO


    lang = (
        "en" if (request.args.get("lang") or "").lower().startswith("en") else "de-CH"
    )
    report = annual.annual_report(_year_arg(year))
    pdf = annual.annual_pdf(report, lang)
    db.session.commit()
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"jahresrechnung-{year}.pdf",
    )


@books_bp.put("/annual/<int:year>/opening")
@permission_required("accounts", "update", "Change the chart of accounts")
def set_opening_balances(year: int):
    """``{"balances": {account number: amount}}`` for an open year whose year
    before is not closed (the first year in Hubra)."""

    body = request.get_json(silent=True) or {}
    balances = body.get("balances")
    if not isinstance(balances, dict):
        raise_error(400, "VALIDATION_ERROR", "balances must be an object")
    annual.set_opening(_year_arg(year), balances)
    log_audit(
        get_current_member().id, "set_opening_balances", "FiscalYear", year, str(year)
    )
    db.session.commit()
    return jsonify(annual.annual_report(year))


@books_bp.post("/annual/<int:year>/close")
@permission_required("accounts", "close", "Close and reopen a fiscal year")
def close_fiscal_year(year: int):
    """Store the closing balances; bookings in the year are refused after."""

    member = get_current_member()
    annual.close_year(_year_arg(year), member.id)
    log_audit(member.id, "close_fiscal_year", "FiscalYear", year, str(year))
    db.session.commit()
    return jsonify(annual.annual_report(year))


@books_bp.post("/annual/<int:year>/reopen")
@permission_required("accounts", "close", "Close and reopen a fiscal year")
def reopen_fiscal_year(year: int):

    annual.reopen_year(_year_arg(year))
    log_audit(
        get_current_member().id, "reopen_fiscal_year", "FiscalYear", year, str(year)
    )
    db.session.commit()
    return jsonify(annual.annual_report(year))

