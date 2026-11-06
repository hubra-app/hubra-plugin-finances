"""Schemas only the books use. Hubra core dropped TransactionUpdateSchema
once the books moved here, so the plugin keeps its own copy."""

from __future__ import annotations

from marshmallow import RAISE, Schema, fields, validate

_PAYMENT_METHODS = ["IBAN", "Card", "Twint", "Cash"]
_TRANSACTION_TYPES = ["income", "expense"]
_TRANSACTION_STATUSES = ["Pending", "Completed"]


class TransactionUpdateSchema(Schema):
    """PATCH: all fields optional."""

    class Meta:
        unknown = RAISE

    status = fields.Str(validate=validate.OneOf(_TRANSACTION_STATUSES))
    description = fields.Str(validate=validate.Length(min=1, max=255))
    date = fields.Date()
    amount = fields.Float(validate=validate.Range(min=0, min_inclusive=False))
    method = fields.Str(validate=validate.OneOf(_PAYMENT_METHODS))
    type = fields.Str(validate=validate.OneOf(_TRANSACTION_TYPES))
    category_id = fields.Int(allow_none=True)
    member_id = fields.Int(allow_none=True)
    payee_name = fields.Str(allow_none=True)
