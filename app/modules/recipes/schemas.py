from marshmallow import Schema, fields, validate


class RecipeItemInputSchema(Schema):
    ingredient_id = fields.Integer(required=True)
    quantity_required = fields.Float(required=True, validate=validate.Range(min=0.001))


class RecipeSaveSchema(Schema):
    product_id = fields.Integer(required=True)
    instructions = fields.String(load_default="")
    items = fields.List(fields.Nested(RecipeItemInputSchema), required=True, validate=validate.Length(min=1))
