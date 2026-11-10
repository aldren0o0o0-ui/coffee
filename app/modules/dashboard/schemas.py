from marshmallow import Schema, fields


class DashboardFilterSchema(Schema):
    start_date = fields.Date(load_default=None)
    end_date = fields.Date(load_default=None)
