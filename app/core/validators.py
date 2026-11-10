import re
from datetime import datetime
from app.core.exceptions import ValidationError


EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
PHONE_REGEX = re.compile(r"^\+?1?\d{9,15}$")
SKU_REGEX = re.compile(r"^[A-Z0-9\-_]{3,20}$")


def validate_email_format(email: str) -> bool:
    """Validate standard email string format."""
    if not email or not EMAIL_REGEX.match(email.strip()):
        raise ValidationError("Invalid email address format.")
    return True


def validate_phone_format(phone: str) -> bool:
    """Validate phone string format."""
    if not phone or not PHONE_REGEX.match(phone.strip()):
        raise ValidationError("Invalid phone number format.")
    return True


def validate_positive_number(value, field_name="Value") -> float:
    """Validate that a number is strictly positive."""
    try:
        val = float(value)
        if val <= 0:
            raise ValidationError(f"{field_name} must be greater than 0.")
        return val
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a valid number.")


def validate_non_negative_number(value, field_name="Value") -> float:
    """Validate that a number is non-negative (>= 0)."""
    try:
        val = float(value)
        if val < 0:
            raise ValidationError(f"{field_name} cannot be negative.")
        return val
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a valid number.")


def validate_sku(sku: str) -> str:
    """Validate SKU format."""
    if not sku or not SKU_REGEX.match(sku.strip().upper()):
        raise ValidationError("SKU must be 3-20 uppercase alphanumeric characters, dashes or underscores.")
    return sku.strip().upper()


def validate_date_range(start_date_str: str, end_date_str: str):
    """Validate start and end date strings."""
    try:
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
        if start and end and start > end:
            raise ValidationError("Start date cannot be after end date.")
        return start, end
    except ValueError:
        raise ValidationError("Dates must be in YYYY-MM-DD format.")
