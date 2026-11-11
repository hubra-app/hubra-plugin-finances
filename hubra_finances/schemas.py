"""Schemas only the books use. Hubra core dropped TransactionUpdateSchema
once the books moved here, so the plugin keeps its own copy."""

from __future__ import annotations

from hubra.core.schemas.finance import TransactionCreateSchema as _CoreCreateSchema
from marshmallow import RAISE, Schema, fields, validate

_PAYMENT_METHODS = ["IBAN", "Card", "Twint", "Cash"]
_TRANSACTION_TYPES = ["income", "expense"]
_TRANSACTION_STATUSES = ["Pending", "Completed"]

# Transaction.amount is Numeric(12, 2) and payee_name String(255): larger
# values are a 400 here instead of a database error (500).
_AMOUNT = validate.Range(min=0, min_inclusive=False, max=1e10, max_inclusive=False)
_PAYEE = validate.Length(max=255)


class TransactionCreateSchema(_CoreCreateSchema):
    """Hubra's create schema with the limits of the columns."""

    payee_name = fields.Str(allow_none=True, load_default=None, validate=_PAYEE)
    amount = fields.Float(required=True, validate=_AMOUNT)


class TransactionUpdateSchema(Schema):
    """PATCH: all fields optional."""

    class Meta:
        unknown = RAISE

    status = fields.Str(validate=validate.OneOf(_TRANSACTION_STATUSES))
    description = fields.Str(validate=validate.Length(min=1, max=255))
    date = fields.Date()
    amount = fields.Float(validate=_AMOUNT)
    method = fields.Str(validate=validate.OneOf(_PAYMENT_METHODS))
    type = fields.Str(validate=validate.OneOf(_TRANSACTION_TYPES))
    category_id = fields.Int(allow_none=True)
    member_id = fields.Int(allow_none=True)
    payee_name = fields.Str(allow_none=True, validate=_PAYEE)
