"""Budgets blueprint: /api/v1/budgets."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from hubra.core.auth.helpers import get_current_member
from hubra.core.permissions import created_by, permission_required
from hubra.core.errors import raise_error
from hubra.core.extensions import db

from .models import Budget
from .services import OWNER_FIELDS, BudgetService, budget_to_dict

budgets_bp = Blueprint("budgets_bp", __name__)


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _actor() -> int:
    return get_current_member().id


# The budget's owner plans it: lines and notes, without budgets.write.
_own_budget = created_by(Budget, column="owner_id", arg="budget_id", reason="owner")


def _owner_only() -> bool:
    return g.get("permission_scope") == "object"


def _done(budget, status=200):
    db.session.commit()
    return jsonify(budget_to_dict(budget, with_lines=True)), status


@budgets_bp.get("/")
@permission_required("budgets", "read", "View budgets")
def list_budgets():
    budgets = BudgetService.list(year=request.args.get("year", type=int))
    return jsonify([budget_to_dict(b) for b in budgets]), 200


@budgets_bp.get("/<int:budget_id>")
@permission_required("budgets", "read", "View budgets", allow=_own_budget)
def get_budget(budget_id: int):
    return jsonify(budget_to_dict(BudgetService.get(budget_id), with_lines=True)), 200


@budgets_bp.post("/")
@permission_required("budgets", "write", "Edit budgets")
def create_budget():
    return _done(BudgetService.create(_body(), _actor()), 201)


@budgets_bp.patch("/<int:budget_id>")
@permission_required("budgets", "write", "Edit budgets", allow=_own_budget)
def update_budget(budget_id: int):
    body = _body()
    if _owner_only() and set(body) - OWNER_FIELDS:
        raise_error(
            403,
            "BUDGET_OWNER",
            "As the budget's owner you can change its lines and notes only",
        )
    return _done(BudgetService.update(budget_id, body, _actor()))


@budgets_bp.delete("/<int:budget_id>")
@permission_required("budgets", "write", "Edit budgets")
def delete_budget(budget_id: int):
    BudgetService.delete(budget_id, _actor())
    db.session.commit()
    return "", 204


@budgets_bp.put("/<int:budget_id>/lines")
@permission_required("budgets", "write", "Edit budgets", allow=_own_budget)
def set_lines(budget_id: int):
    return _done(BudgetService.set_lines(budget_id, _body().get("lines"), _actor()))


@budgets_bp.post("/<int:budget_id>/copy")
@permission_required("budgets", "write", "Edit budgets")
def copy_budget(budget_id: int):
    return _done(BudgetService.copy(budget_id, _body().get("year"), _actor()), 201)
