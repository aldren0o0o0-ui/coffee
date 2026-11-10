from decimal import Decimal, ROUND_HALF_UP
from app.core.exceptions import ValidationError

# Conversion factors to canonical base units (WEIGHT: grams, VOLUME: milliliters)
WEIGHT_FACTORS_TO_G = {
    "g": Decimal("1.0"),
    "gram": Decimal("1.0"),
    "grams": Decimal("1.0"),
    "kg": Decimal("1000.0"),
    "kilogram": Decimal("1000.0"),
    "kilograms": Decimal("1000.0"),
    "oz": Decimal("28.3495"),
    "ounce": Decimal("28.3495"),
    "ounces": Decimal("28.3495"),
    "lb": Decimal("453.592"),
    "pound": Decimal("453.592"),
    "pounds": Decimal("453.592"),
}

VOLUME_FACTORS_TO_ML = {
    "ml": Decimal("1.0"),
    "milliliter": Decimal("1.0"),
    "milliliters": Decimal("1.0"),
    "l": Decimal("1000.0"),
    "liter": Decimal("1000.0"),
    "liters": Decimal("1000.0"),
    "fl oz": Decimal("29.5735"),
    "floz": Decimal("29.5735"),
    "cup": Decimal("240.0"),
    "cups": Decimal("240.0"),
    "tbsp": Decimal("15.0"),
    "tsp": Decimal("5.0"),
}

COUNT_UNITS = {"pcs", "piece", "pieces", "pack", "box", "bottle", "unit", "units"}


def normalize_unit(unit_str: str) -> str:
    """Normalize unit string for standard matching."""
    if not unit_str:
        return ""
    return unit_str.strip().lower()


def get_unit_category(unit_str: str) -> str:
    """Determine the physical category of a measurement unit."""
    norm = normalize_unit(unit_str)
    if norm in WEIGHT_FACTORS_TO_G:
        return "WEIGHT"
    if norm in VOLUME_FACTORS_TO_ML:
        return "VOLUME"
    if norm in COUNT_UNITS:
        return "COUNT"
    return "UNKNOWN"


def are_units_compatible(from_unit: str, to_unit: str) -> bool:
    """Check whether two units can be converted safely."""
    u1 = normalize_unit(from_unit)
    u2 = normalize_unit(to_unit)
    if u1 == u2:
        return True
    cat1 = get_unit_category(u1)
    cat2 = get_unit_category(u2)
    return cat1 != "UNKNOWN" and cat1 == cat2


def convert_quantity(quantity, from_unit: str, to_unit: str) -> Decimal:
    """
    Safely convert a quantity between compatible units using exact Decimal math.
    Raises ValidationError if units are incompatible.
    """
    qty = Decimal(str(quantity))
    u1 = normalize_unit(from_unit)
    u2 = normalize_unit(to_unit)

    if not u1 or not u2 or u1 == u2:
        return qty

    cat1 = get_unit_category(u1)
    cat2 = get_unit_category(u2)

    if cat1 != cat2 or cat1 == "UNKNOWN":
        raise ValidationError(
            f"Incompatible unit conversion from '{from_unit}' ({cat1}) to '{to_unit}' ({cat2}). "
            f"Cannot convert different measurement dimensions without explicit density specifications."
        )

    if cat1 == "WEIGHT":
        base_g = qty * WEIGHT_FACTORS_TO_G[u1]
        converted = base_g / WEIGHT_FACTORS_TO_G[u2]
        return converted.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if cat1 == "VOLUME":
        base_ml = qty * VOLUME_FACTORS_TO_ML[u1]
        converted = base_ml / VOLUME_FACTORS_TO_ML[u2]
        return converted.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if cat1 == "COUNT":
        if u1 == u2:
            return qty
        raise ValidationError(f"Direct count unit conversion between '{from_unit}' and '{to_unit}' is not supported.")

    return qty
