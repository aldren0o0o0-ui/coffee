import re
from decimal import Decimal, InvalidOperation
from app.core.exceptions import ValidationError
from app.modules.catalog.models import Product, Category, ProductVariant


SKU_REGEX = re.compile(r"^[A-Z0-9_-]{2,32}$")
SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    """Generate normalized URL-friendly slug from text."""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def validate_category_name(name: str, exclude_id=None) -> str:
    if not name or not name.strip():
        raise ValidationError("Category name is required.")
    name = name.strip()
    if len(name) < 2 or len(name) > 64:
        raise ValidationError("Category name must be between 2 and 64 characters.")

    query = Category.query.filter(Category.name.ilike(name))
    if exclude_id:
        query = query.filter(Category.id != exclude_id)
    if query.first():
        raise ValidationError(f"Category '{name}' already exists.")
    return name


def validate_category_slug(slug: str, exclude_id=None) -> str:
    if not slug or not slug.strip():
        raise ValidationError("Category slug is required.")
    slug = slugify(slug)
    if not SLUG_REGEX.match(slug):
        raise ValidationError("Slug contains invalid characters. Use lowercase letters, numbers, and hyphens.")

    query = Category.query.filter_by(slug=slug)
    if exclude_id:
        query = query.filter(Category.id != exclude_id)
    if query.first():
        raise ValidationError(f"Category slug '{slug}' is already in use.")
    return slug


def validate_product_sku(sku: str, exclude_id=None) -> str:
    if not sku or not sku.strip():
        raise ValidationError("SKU is required.")
    sku = sku.strip().upper()
    if not SKU_REGEX.match(sku):
        raise ValidationError("SKU must be 2-32 characters long containing only letters, digits, dashes, and underscores.")

    # Check uniqueness in Product table
    prod_query = Product.query.filter_by(sku=sku)
    if exclude_id:
        prod_query = prod_query.filter(Product.id != exclude_id)
    if prod_query.first():
        raise ValidationError(f"Product SKU '{sku}' is already in use.")

    # Check uniqueness in ProductVariant table
    var_query = ProductVariant.query.filter_by(sku=sku)
    if var_query.first():
        raise ValidationError(f"SKU '{sku}' is already in use by a product variant.")

    return sku


def validate_variant_sku(sku: str, exclude_variant_id=None) -> str:
    if not sku or not sku.strip():
        raise ValidationError("Variant SKU is required.")
    sku = sku.strip().upper()
    if not SKU_REGEX.match(sku):
        raise ValidationError("Variant SKU must be 2-32 characters containing only uppercase letters, numbers, dashes, and underscores.")

    # Check Product table
    if Product.query.filter_by(sku=sku).first():
        raise ValidationError(f"SKU '{sku}' is already in use by a product.")

    # Check ProductVariant table
    var_query = ProductVariant.query.filter_by(sku=sku)
    if exclude_variant_id:
        var_query = var_query.filter(ProductVariant.id != exclude_variant_id)
    if var_query.first():
        raise ValidationError(f"Variant SKU '{sku}' is already in use.")

    return sku


def validate_price(value, field_name="Price") -> Decimal:
    if value is None or str(value).strip() == "":
        raise ValidationError(f"{field_name} is required.")
    try:
        dec_val = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid number.")

    if dec_val < Decimal("0.00"):
        raise ValidationError(f"{field_name} cannot be negative.")
    return dec_val


# Backwards compatibility aliases
validate_unique_product_sku = validate_product_sku
validate_unique_category_name = validate_category_name
