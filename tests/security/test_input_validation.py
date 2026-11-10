import pytest
from app.core.validators import validate_email_format, validate_positive_number, validate_sku
from app.core.exceptions import ValidationError


def test_input_validation_rules():
    # Email format validation
    assert validate_email_format("admin@coffee.local") is True
    with pytest.raises(ValidationError):
        validate_email_format("not-an-email")

    # Positive number validation
    assert validate_positive_number(12.50) == 12.50
    with pytest.raises(ValidationError):
        validate_positive_number(-5.0)
    with pytest.raises(ValidationError):
        validate_positive_number("not-a-number")

    # SKU format validation
    assert validate_sku("esp-lat-12") == "ESP-LAT-12"
    with pytest.raises(ValidationError):
        validate_sku("??bad_sku!!")
