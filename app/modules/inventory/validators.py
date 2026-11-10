import re
from decimal import Decimal, InvalidOperation
from app.core.exceptions import ValidationError
from app.modules.inventory.models import Ingredient, Supplier, InventoryCategory


SKU_REGEX = re.compile(r"^[A-Z0-9_-]{2,32}$")
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def validate_inventory_name(name: str, exclude_id=None) -> str:
    if not name or not name.strip():
        raise ValidationError("Inventory item name is required.")
    name = name.strip()
    if len(name) < 2 or len(name) > 120:
        raise ValidationError("Inventory item name must be between 2 and 120 characters.")

    query = Ingredient.query.filter(Ingredient.name.ilike(name))
    if exclude_id:
        query = query.filter(Ingredient.id != exclude_id)
    if query.first():
        raise ValidationError(f"Inventory item '{name}' already exists.")
    return name


def validate_inventory_sku(sku: str, exclude_id=None) -> str:
    if not sku or not sku.strip():
        raise ValidationError("SKU is required.")
    sku = sku.strip().upper()
    if not SKU_REGEX.match(sku):
        raise ValidationError("SKU must be 2-32 characters long containing only letters, numbers, hyphens, and underscores.")

    query = Ingredient.query.filter_by(sku=sku)
    if exclude_id:
        query = query.filter(Ingredient.id != exclude_id)
    if query.first():
        raise ValidationError(f"Inventory SKU '{sku}' is already in use.")
    return sku


def validate_quantity(value, field_name="Quantity", allow_negative=False) -> Decimal:
    if value is None or str(value).strip() == "":
        raise ValidationError(f"{field_name} is required.")
    try:
        dec_val = Decimal(str(value)).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid numeric quantity.")

    if not allow_negative and dec_val < Decimal("0.0000"):
        raise ValidationError(f"{field_name} cannot be negative.")
    return dec_val


def validate_cost(value, field_name="Cost per unit") -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal("0.0000")
    try:
        dec_val = Decimal(str(value)).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid numeric cost.")

    if dec_val < Decimal("0.0000"):
        raise ValidationError(f"{field_name} cannot be negative.")
    return dec_val


def validate_adjustment_reason(reason: str) -> str:
    if not reason or not reason.strip():
        raise ValidationError("A reason is mandatory for manual stock adjustments.")
    reason = reason.strip()
    if len(reason) < 3:
        raise ValidationError("Adjustment reason must be at least 3 characters long.")
    return reason


def validate_supplier(name: str, email: str = None, phone: str = None, exclude_id=None) -> str:
    if not name or not name.strip():
        raise ValidationError("Supplier name is required.")
    name = name.strip()

    query = Supplier.query.filter(Supplier.name.ilike(name))
    if exclude_id:
        query = query.filter(Supplier.id != exclude_id)
    if query.first():
        raise ValidationError(f"Supplier '{name}' already exists.")

    if email and email.strip():
        email = email.strip().lower()
        if not EMAIL_REGEX.match(email):
            raise ValidationError("Invalid supplier email address format.")

    return name


# Backwards compatibility
validate_unique_ingredient_name = validate_inventory_name
validate_stock_quantity = validate_quantity
