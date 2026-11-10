from marshmallow import Schema, fields


class StoreSettingsUpdateSchema(Schema):
    store_name = fields.String(required=True)
    currency_symbol = fields.String(load_default="₱")
    tax_rate = fields.Float(load_default=0.08)
    receipt_header = fields.String(load_default="")
    receipt_footer = fields.String(load_default="")
