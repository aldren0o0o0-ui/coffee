from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.core.exceptions import ValidationError
from app.modules.catalog.models import Product, ProductVariant
from app.modules.inventory.models import Ingredient
from app.modules.recipes.units import are_units_compatible


def validate_recipe_data(product_id=None, product_variant_id=None, items_data=None, yield_quantity=1.0):
    """Validate recipe formulation data before persistence."""
    if not product_id and not product_variant_id:
        raise ValidationError("Recipe must be associated with a Product or a Product Variant.")

    if product_variant_id:
        variant = db.session.get(ProductVariant, product_variant_id)
        if not variant or not variant.is_active:
            raise ValidationError("Specified product variant does not exist or is inactive.")
        if product_id and variant.product_id != int(product_id):
            raise ValidationError("Product variant does not belong to the specified product.")

    if product_id:
        product = db.session.get(Product, product_id)
        if not product or not product.is_active:
            raise ValidationError("Specified product does not exist or is inactive.")

    try:
        y_qty = Decimal(str(yield_quantity or 1.0))
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("Invalid yield quantity.")

    if y_qty <= Decimal("0.0"):
        raise ValidationError("Recipe yield quantity must be greater than zero.")

    validate_recipe_items(items_data)
    return True


def validate_recipe_items(items):
    """Validate individual ingredient lines within a recipe."""
    if not items or len(items) == 0:
        raise ValidationError("A recipe must include at least one raw ingredient component.")

    seen_ingredients = set()
    for idx, item in enumerate(items, 1):
        ing_id = item.get("ingredient_id")
        if not ing_id:
            raise ValidationError(f"Ingredient line #{idx} is missing an ingredient reference.")

        try:
            ing_id_int = int(ing_id)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid ingredient ID '{ing_id}' on line #{idx}.")

        if ing_id_int in seen_ingredients:
            raise ValidationError(f"Duplicate ingredient detected (ID: {ing_id_int}). Each ingredient may only be added once per recipe.")
        seen_ingredients.add(ing_id_int)

        # Verify ingredient exists and is active
        ingredient = db.session.get(Ingredient, ing_id_int)
        if not ingredient or not ingredient.is_active:
            raise ValidationError(f"Ingredient with ID {ing_id_int} does not exist or is inactive.")

        try:
            qty = Decimal(str(item.get("quantity_required", 0)))
        except (ValueError, TypeError, InvalidOperation):
            raise ValidationError(f"Invalid quantity value for ingredient '{ingredient.name}'.")

        if qty <= Decimal("0.0"):
            raise ValidationError(f"Ingredient quantity for '{ingredient.name}' must be greater than zero.")

        # Check unit compatibility if recipe specifies custom unit
        recipe_unit = item.get("unit")
        if recipe_unit and ingredient.unit:
            if not are_units_compatible(recipe_unit, ingredient.unit):
                raise ValidationError(
                    f"Unit '{recipe_unit}' for ingredient '{ingredient.name}' is incompatible with its inventory unit '{ingredient.unit}'."
                )

    return True
