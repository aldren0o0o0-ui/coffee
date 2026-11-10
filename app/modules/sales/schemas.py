from marshmallow import Schema, fields, validate


class SaleRefundSchema(Schema):
    reason = fields.String(required=True, validate=validate.Length(min=3, max=255))
