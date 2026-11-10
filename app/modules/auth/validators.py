from app.core.exceptions import ValidationError
from app.core.validators import validate_email_format


def validate_password_strength(password: str):
    """Ensure password meets minimum complexity requirements."""
    if not password or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not any(c.isnumeric() for c in password):
        raise ValidationError("Password must contain at least one number.")
    return True


def validate_login_payload(username, password):
    if not username or not username.strip():
        raise ValidationError("Username is required.")
    if not password:
        raise ValidationError("Password is required.")
    return True
