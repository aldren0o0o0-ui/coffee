from marshmallow import Schema, fields, validate


class OpenShiftSchema(Schema):
    opening_cash = fields.Float(required=True, validate=validate.Range(min=0.0))
    notes = fields.String(load_default="")


class CloseShiftSchema(Schema):
    closing_cash = fields.Float(required=True, validate=validate.Range(min=0.0))
    notes = fields.String(load_default="")


class CartItemSchema(Schema):
    product_id = fields.Integer(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=1))
    notes = fields.String(load_default="")


class POSCheckoutSchema(Schema):
    items = fields.List(fields.Nested(CartItemSchema), required=True, validate=validate.Length(min=1))
    payment_method = fields.String(required=True, validate=validate.OneOf(["Cash", "Card", "QR", "Split"]))
    cash_tendered = fields.Float(load_default=0.0)
    customer_name = fields.String(load_default="Guest")
    discount_amount = fields.Float(load_default=0.0)
    notes = fields.String(load_default="")
