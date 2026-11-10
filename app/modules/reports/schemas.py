from marshmallow import Schema, fields


class ReportDateRangeSchema(Schema):
    start_date = fields.Date(load_default=None)
    end_date = fields.Date(load_default=None)
    report_type = fields.String(load_default="summary")
