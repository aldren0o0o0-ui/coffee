from marshmallow import Schema, fields, validate


class EmployeeProfileSchema(Schema):
    phone = fields.String(load_default="")
    hourly_rate = fields.Float(load_default=15.0, validate=validate.Range(min=0.0))
    hire_date = fields.Date(load_default=None)
    emergency_contact = fields.String(load_default="")


class ClockInOutSchema(Schema):
    notes = fields.String(load_default="")
