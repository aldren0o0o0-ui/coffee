from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db
from app.modules.recipes.units import convert_quantity, are_units_compatible


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    product_variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    prep_notes = db.Column(db.Text, nullable=True)
    yield_quantity = db.Column(db.Numeric(10, 2), default=Decimal("1.00"), nullable=False)
    yield_unit = db.Column(db.String(32), default="serving", nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    product = db.relationship("Product", foreign_keys=[product_id], lazy="joined")
    variant = db.relationship("ProductVariant", foreign_keys=[product_variant_id], lazy="joined")
    items = db.relationship(
        "RecipeItem",
        backref="recipe",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="RecipeItem.display_order.asc()"
    )

    @property
    def target_name(self) -> str:
        """User-friendly target product and/or variant name."""
        if self.variant and self.product:
            return f"{self.product.name} ({self.variant.name})"
        if self.product:
            return self.product.name
        if self.variant:
            return self.variant.name
        return self.name or "Unnamed Formulation"

    @property
    def target_price(self) -> Decimal:
        """Selling price of the associated product or variant."""
        if self.variant and self.variant.price is not None:
            return Decimal(str(self.variant.price))
        if self.product and self.product.base_price is not None:
            return Decimal(str(self.product.base_price))
        return Decimal("0.00")

    @property
    def total_cost_decimal(self) -> Decimal:
        """Calculate total ingredient cost to prepare one yield of this recipe using Decimal."""
        total = Decimal("0.0000")
        for item in self.items:
            total += item.item_cost_decimal
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total_cost(self) -> float:
        """Legacy float representation for backward compatibility."""
        return float(self.total_cost_decimal)

    @property
    def cost_per_yield(self) -> Decimal:
        """Unit cost per serving yield."""
        qty = Decimal(str(self.yield_quantity or 1.0))
        if qty <= Decimal("0.0"):
            qty = Decimal("1.0")
        return (self.total_cost_decimal / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def gross_margin_percentage(self) -> float:
        """Calculate gross profit margin percentage against target selling price."""
        price = self.target_price
        if price <= Decimal("0.00"):
            return 0.0
        cost = self.total_cost_decimal
        margin = ((price - cost) / price) * Decimal("100.0")
        return round(float(margin), 1)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_variant_id": self.product_variant_id,
            "product_name": self.product.name if self.product else "",
            "variant_name": self.variant.name if self.variant else None,
            "target_name": self.target_name,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "prep_notes": self.prep_notes,
            "yield_quantity": float(self.yield_quantity),
            "yield_unit": self.yield_unit,
            "version": self.version,
            "is_active": self.is_active,
            "total_cost": self.total_cost,
            "target_price": float(self.target_price),
            "gross_margin": self.gross_margin_percentage,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class RecipeItem(db.Model):
    __tablename__ = "recipe_items"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity_required = db.Column(db.Numeric(12, 4), nullable=False)
    unit = db.Column(db.String(16), default="g", nullable=False)
    unit_of_measure_id = db.Column(db.Integer, db.ForeignKey("units_of_measure.id", ondelete="SET NULL"), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    ingredient = db.relationship("Ingredient", lazy="joined")
    unit_of_measure = db.relationship("UnitOfMeasure", lazy="joined")

    @property
    def item_cost_decimal(self) -> Decimal:
        """Calculate item ingredient cost taking unit conversions into account."""
        if not self.ingredient:
            return Decimal("0.0000")

        cost_per_ing_unit = Decimal(str(self.ingredient.cost_per_unit or 0))
        ing_unit = self.ingredient.unit or "g"
        recipe_unit = self.unit or ing_unit

        try:
            # Convert recipe quantity into ingredient's inventory unit
            needed_in_ing_unit = convert_quantity(self.quantity_required, recipe_unit, ing_unit)
            return (needed_in_ing_unit * cost_per_ing_unit).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        except Exception:
            # Fallback if unit mismatch cannot be converted directly
            return (Decimal(str(self.quantity_required)) * cost_per_ing_unit).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    @property
    def item_cost(self) -> float:
        return float(self.item_cost_decimal)

    def to_dict(self):
        return {
            "id": self.id,
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient.name if self.ingredient else "",
            "ingredient_unit": self.ingredient.unit if self.ingredient else "",
            "unit": self.unit,
            "quantity_required": float(self.quantity_required),
            "notes": self.notes,
            "display_order": self.display_order,
            "item_cost": round(self.item_cost, 4)
        }
