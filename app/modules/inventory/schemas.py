from marshmallow import Schema, fields, validate
from app.modules.inventory.models import StockMovementType


class SupplierSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    contact_person = fields.String(load_default="")
    email = fields.Email(load_default=None)
    phone = fields.String(load_default="")
    address = fields.String(load_default="")


class IngredientSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    sku = fields.String(required=False)
    unit = fields.String(required=True, validate=validate.OneOf(["g", "ml", "pcs", "oz"]))
    current_stock = fields.Float(load_default=0.0)
    minimum_stock = fields.Float(load_default=10.0)
    cost_per_unit = fields.Float(load_default=0.0)
    supplier_id = fields.Integer(load_default=None)


class StockMovementCreateSchema(Schema):
    ingredient_id = fields.Integer(required=True)
    movement_type = fields.String(required=True, validate=validate.OneOf(StockMovementType.ALL))
    quantity = fields.Float(required=True)
    notes = fields.String(load_default="")
    reference = fields.String(load_default="")
