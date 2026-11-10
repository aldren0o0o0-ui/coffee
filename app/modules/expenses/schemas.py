from marshmallow import Schema, fields, validate


class ExpenseCategorySchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=64))
    description = fields.String(load_default="")


class ExpenseCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=2, max=120))
    category_id = fields.Integer(required=True)
    amount = fields.Float(required=True, validate=validate.Range(min=0.01))
    expense_date = fields.Date(load_default=None)
    notes = fields.String(load_default="")
