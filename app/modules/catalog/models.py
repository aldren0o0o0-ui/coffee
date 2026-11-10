from datetime import datetime
from app.extensions import db
from sqlalchemy import CheckConstraint


product_option_group_associations = db.Table(
    "product_option_group_associations",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    db.Column("option_group_id", db.Integer, db.ForeignKey("product_option_groups.id", ondelete="CASCADE"), primary_key=True)
)


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("display_order >= 0", name="ck_category_display_order_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    products = db.relationship("Product", backref="category", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "product_count": self.products.filter_by(is_active=True).count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="ck_product_base_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_product_cost_price_non_negative"),
        CheckConstraint("display_order >= 0", name="ck_product_display_order_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), nullable=False, index=True)
    sku = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    variants = db.relationship("ProductVariant", backref="product", lazy="dynamic", cascade="all, delete-orphan")
    option_groups = db.relationship("ProductOptionGroup", secondary=product_option_group_associations, backref=db.backref("products", lazy="dynamic"))
    # Deferred to Phase 5 (Recipes) and Phase 7 (Sales):
    # recipe = db.relationship("Recipe", backref="product", uselist=False, cascade="all, delete-orphan")
    # sale_items = db.relationship("SaleItem", backref="product", lazy="dynamic")

    @property
    def has_variants(self) -> bool:
        return self.variants.filter_by(is_active=True).count() > 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "sku": self.sku,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "base_price": float(self.base_price),
            "cost_price": float(self.cost_price),
            "description": self.description,
            "image_url": self.image_url,
            "is_available": self.is_available,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "has_variants": self.has_variants,
            "variants": [v.to_dict() for v in self.variants.filter_by(is_active=True)],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ProductVariant(db.Model):
    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_variant_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_variant_cost_price_non_negative"),
        CheckConstraint("display_order >= 0", name="ck_variant_display_order_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)  # e.g., "Small", "Medium", "Large Hot", "Large Iced"
    sku = db.Column(db.String(32), unique=True, nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.name,
            "sku": self.sku,
            "price": float(self.price),
            "cost_price": float(self.cost_price),
            "is_available": self.is_available,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ProductOptionGroup(db.Model):
    __tablename__ = "product_option_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)  # e.g., "Milk Choice", "Temperature", "Extras"
    is_required = db.Column(db.Boolean, default=False, nullable=False)
    max_select = db.Column(db.Integer, default=1, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    options = db.relationship("ProductOption", backref="group", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_required": self.is_required,
            "max_select": self.max_select,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "options": [opt.to_dict() for opt in self.options.filter_by(is_available=True)]
        }


class ProductOption(db.Model):
    __tablename__ = "product_options"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("product_option_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)  # e.g., "Whole Milk", "Oat Milk", "Extra Shot"
    price_adjustment = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "name": self.name,
            "price_adjustment": float(self.price_adjustment),
            "is_available": self.is_available,
            "display_order": self.display_order
        }
