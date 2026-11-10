from datetime import datetime
from decimal import Decimal
from app.extensions import db
from sqlalchemy import CheckConstraint


class UnitCategory:
    WEIGHT = "WEIGHT"
    VOLUME = "VOLUME"
    COUNT = "COUNT"
    PACKAGING = "PACKAGING"
    ALL = [WEIGHT, VOLUME, COUNT, PACKAGING]


class UnitOfMeasure(db.Model):
    __tablename__ = "units_of_measure"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)  # e.g., KG, G, L, ML, PCS
    name = db.Column(db.String(64), nullable=False)  # e.g., Kilogram, Gram
    category = db.Column(db.String(32), nullable=False)  # WEIGHT, VOLUME, COUNT, PACKAGING
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "is_active": self.is_active
        }


class InventoryCategory(db.Model):
    __tablename__ = "inventory_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "item_count": self.items.filter_by(is_active=True).count() if hasattr(self, "items") else 0
        }


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    contact_person = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_person": self.contact_person,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }


class Ingredient(db.Model):
    """Raw Material Inventory Item model."""
    __tablename__ = "ingredients"
    __table_args__ = (
        CheckConstraint("current_quantity >= 0", name="ck_ingredient_current_quantity_non_negative"),
        CheckConstraint("minimum_stock_level >= 0", name="ck_ingredient_min_stock_non_negative"),
        CheckConstraint("reorder_level >= 0", name="ck_ingredient_reorder_level_non_negative"),
        CheckConstraint("cost_per_unit >= 0", name="ck_ingredient_cost_per_unit_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    sku = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("inventory_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_of_measure_id = db.Column(db.Integer, db.ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=True, index=True)
    unit = db.Column(db.String(16), nullable=False, default="g")  # Legacy unit string
    current_quantity = db.Column(db.Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    minimum_stock_level = db.Column(db.Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    reorder_level = db.Column(db.Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    maximum_stock_level = db.Column(db.Numeric(12, 4), nullable=True)
    cost_per_unit = db.Column(db.Numeric(10, 4), default=Decimal("0.0000"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    unit_of_measure = db.relationship("UnitOfMeasure", backref="items")
    category = db.relationship("InventoryCategory", backref=db.backref("items", lazy="dynamic"))
    supplier = db.relationship("Supplier", backref="ingredients")
    # Deferred to Phase 5 (Recipes):
    # recipe_items = db.relationship("RecipeItem", backref="ingredient", lazy="dynamic")
    movements = db.relationship("StockMovement", backref="ingredient", lazy="dynamic", cascade="all, delete-orphan")
    purchase_items = db.relationship("PurchaseItem", backref="ingredient", lazy="dynamic")

    # Backwards compatibility properties
    @property
    def current_stock(self) -> float:
        return float(self.current_quantity) if self.current_quantity is not None else 0.0

    @current_stock.setter
    def current_stock(self, value):
        self.current_quantity = Decimal(str(value))

    @property
    def minimum_stock(self) -> float:
        return float(self.minimum_stock_level) if self.minimum_stock_level is not None else 0.0

    @minimum_stock.setter
    def minimum_stock(self, value):
        self.minimum_stock_level = Decimal(str(value))

    @property
    def is_out_of_stock(self) -> bool:
        return self.current_quantity <= Decimal("0")

    @property
    def is_low_stock(self) -> bool:
        threshold = self.reorder_level if self.reorder_level > Decimal("0") else self.minimum_stock_level
        return self.current_quantity <= threshold and self.current_quantity > Decimal("0")

    @property
    def stock_status(self) -> str:
        if self.is_out_of_stock:
            return "OUT_OF_STOCK"
        elif self.is_low_stock:
            return "LOW_STOCK"
        return "IN_STOCK"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "unit": self.unit_of_measure.code if self.unit_of_measure else self.unit,
            "unit_of_measure_id": self.unit_of_measure_id,
            "current_quantity": float(self.current_quantity),
            "minimum_stock_level": float(self.minimum_stock_level),
            "reorder_level": float(self.reorder_level),
            "maximum_stock_level": float(self.maximum_stock_level) if self.maximum_stock_level else None,
            "cost_per_unit": float(self.cost_per_unit),
            "is_low_stock": self.is_low_stock,
            "is_out_of_stock": self.is_out_of_stock,
            "stock_status": self.stock_status,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "is_active": self.is_active
        }


# Alias for explicit domain naming
InventoryItem = Ingredient


class StockMovementType:
    PURCHASE = "purchase"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    INITIAL_STOCK = "initial_stock"
    WASTE = "waste"
    CORRECTION = "correction"
    CONSUMPTION = "consumption"  # Reserved for Phase 5
    ALL = [PURCHASE, ADJUSTMENT_IN, ADJUSTMENT_OUT, INITIAL_STOCK, WASTE, CORRECTION, CONSUMPTION]


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type = db.Column(db.String(32), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 4), nullable=False)  # Positive for additions, negative for deductions
    unit_cost = db.Column(db.Numeric(10, 4), default=Decimal("0.0000"), nullable=False)
    reference_type = db.Column(db.String(32), nullable=True)  # PURCHASE_ORDER, MANUAL_ADJUSTMENT, AUDIT_CORRECTION
    reference_id = db.Column(db.Integer, nullable=True)
    reference = db.Column(db.String(120), nullable=True)  # e.g., PO #1001, Inv #456
    reason = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship to user
    created_by = db.relationship("User", backref="stock_movements")

    @property
    def unit(self):
        return self.ingredient.unit if self.ingredient else ""

    def to_dict(self):
        return {
            "id": self.id,
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient.name if self.ingredient else "",
            "movement_type": self.movement_type,
            "quantity": float(self.quantity),
            "unit": self.ingredient.unit if self.ingredient else "",
            "unit_cost": float(self.unit_cost),
            "reference_type": self.reference_type,
            "reference": self.reference,
            "reason": self.reason,
            "notes": self.notes,
            "created_by": self.created_by.full_name if self.created_by else "System",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }


class PurchaseStatus:
    DRAFT = "DRAFT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"
    ALL = [DRAFT, RECEIVED, CANCELLED]


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    reference_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(32), default=PurchaseStatus.DRAFT, nullable=False, index=True)
    total_cost = db.Column(db.Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    supplier = db.relationship("Supplier", backref="purchases")
    items = db.relationship("PurchaseItem", backref="purchase", lazy="dynamic", cascade="all, delete-orphan")
    created_by = db.relationship("User", backref="purchases")

    def to_dict(self):
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else "",
            "reference_number": self.reference_number,
            "purchase_date": self.purchase_date.strftime("%Y-%m-%d"),
            "status": self.status,
            "total_cost": float(self.total_cost),
            "notes": self.notes,
            "items_count": self.items.count(),
            "created_by": self.created_by.full_name if self.created_by else "System",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(10, 4), nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "purchase_id": self.purchase_id,
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient.name if self.ingredient else "",
            "quantity": float(self.quantity),
            "unit": self.ingredient.unit if self.ingredient else "",
            "unit_cost": float(self.unit_cost),
            "line_total": float(self.line_total)
        }
