from marshmallow import Schema, fields, validate
from app.core.permissions import Roles


class UserCreateSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=64))
    email = fields.Email(required=True)
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    role = fields.String(required=True, validate=validate.OneOf(Roles.ALL))
    is_active = fields.Boolean(load_default=True)


class UserUpdateSchema(Schema):
    email = fields.Email(required=False)
    full_name = fields.String(required=False, validate=validate.Length(min=2, max=120))
    role = fields.String(required=False, validate=validate.OneOf(Roles.ALL))
    is_active = fields.Boolean(required=False)
    password = fields.String(required=False, validate=validate.Length(min=8, max=128))
