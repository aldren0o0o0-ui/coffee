from marshmallow import Schema, fields, validate


class CategorySchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=2, max=64))
    description = fields.String(load_default="")
    display_order = fields.Integer(load_default=0)
    is_active = fields.Boolean(load_default=True)


class ProductSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    sku = fields.String(required=False)
    category_id = fields.Integer(required=True)
    base_price = fields.Float(required=True, validate=validate.Range(min=0.01))
    cost_price = fields.Float(load_default=0.0, validate=validate.Range(min=0.0))
    description = fields.String(load_default="")
    is_available = fields.Boolean(load_default=True)
