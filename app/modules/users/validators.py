from app.core.exceptions import ValidationError
from app.core.permissions import Roles
from app.modules.users.models import User


def validate_user_role(role: str):
    if role not in Roles.ALL:
        raise ValidationError(f"Invalid role: {role}. Must be one of {', '.join(Roles.ALL)}")
    return role


def validate_unique_username(username: str, exclude_user_id=None):
    query = User.query.filter_by(username=username.strip())
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise ValidationError(f"Username '{username}' is already taken.")


def validate_unique_email(email: str, exclude_user_id=None):
    query = User.query.filter_by(email=email.strip().lower())
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise ValidationError(f"Email '{email}' is already registered.")
