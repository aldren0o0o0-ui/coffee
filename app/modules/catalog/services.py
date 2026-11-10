from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.modules.catalog.models import Category, Product, ProductVariant, ProductOptionGroup, ProductOption
from app.modules.catalog.validators import (
    validate_category_name,
    validate_category_slug,
    validate_product_sku,
    validate_variant_sku,
    validate_price,
    slugify
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_query
from app.core.utilities import generate_sku


class CatalogService:
    @staticmethod
    def get_categories(active_only=False):
        query = Category.query.order_by(Category.display_order.asc(), Category.name.asc())
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()

    @staticmethod
    def get_category_by_id(category_id):
        cat = db.session.get(Category, category_id)
        if not cat:
            raise NotFoundError("Category not found.")
        return cat

    @staticmethod
    def get_category_by_slug(slug):
        cat = Category.query.filter_by(slug=slug).first()
        if not cat:
            raise NotFoundError("Category not found.")
        return cat

    @staticmethod
    def create_category(name, description="", display_order=0, slug=None):
        name = validate_category_name(name)
        if not slug or not slug.strip():
            slug = slugify(name)
        slug = validate_category_slug(slug)

        display_order = max(0, int(display_order or 0))

        cat = Category(
            name=name,
            slug=slug,
            description=description.strip() if description else "",
            display_order=display_order,
            is_active=True
        )
        db.session.add(cat)
        db.session.commit()
        return cat

    @staticmethod
    def update_category(category_id, name=None, description=None, display_order=None, is_active=None, slug=None):
        cat = CatalogService.get_category_by_id(category_id)

        if name is not None and name.strip() != cat.name:
            cat.name = validate_category_name(name, exclude_id=cat.id)
            if not slug:
                # auto-update slug if not explicitly given
                new_slug = slugify(cat.name)
                cat.slug = validate_category_slug(new_slug, exclude_id=cat.id)

        if slug is not None and slug.strip() != cat.slug:
            cat.slug = validate_category_slug(slug, exclude_id=cat.id)

        if description is not None:
            cat.description = description.strip()

        if display_order is not None:
            cat.display_order = max(0, int(display_order))

        if is_active is not None:
            cat.is_active = bool(is_active)

        cat.updated_at = datetime.utcnow()
        db.session.commit()
        return cat

    @staticmethod
    def delete_category(category_id):
        cat = CatalogService.get_category_by_id(category_id)
        active_products_count = cat.products.filter_by(is_active=True).count()
        if active_products_count > 0:
            raise ValidationError(
                f"Cannot delete category '{cat.name}' because it contains {active_products_count} active product(s). "
                "Please deactivate or reassign the products first."
            )
        # Soft-deactivate if products exist historically, or delete if empty
        if cat.products.count() > 0:
            cat.is_active = False
            db.session.commit()
            return cat
        else:
            db.session.delete(cat)
            db.session.commit()
            return None

    @staticmethod
    def get_products_paginated(page=1, per_page=15, category_id=None, search=None, available_only=False, active_only=False):
        query = Product.query
        if active_only:
            query = query.filter_by(is_active=True)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if available_only:
            query = query.filter_by(is_available=True)
        if search:
            s = f"%{search.strip()}%"
            query = query.filter((Product.name.ilike(s)) | (Product.sku.ilike(s)))
        query = query.order_by(Product.display_order.asc(), Product.name.asc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_product_by_id(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            raise NotFoundError("Product not found.")
        return product

    @staticmethod
    def get_product_by_sku(sku):
        product = Product.query.filter_by(sku=sku.strip().upper()).first()
        if not product:
            raise NotFoundError("Product not found.")
        return product

    @staticmethod
    def create_product(name, category_id, base_price, sku=None, cost_price=0.0, description="",
                       is_available=True, is_active=True, display_order=0, image_url=None, variants_data=None):
        if not name or not name.strip():
            raise ValidationError("Product name is required.")
        name = name.strip()

        cat = CatalogService.get_category_by_id(category_id)

        # SKU generation or validation
        if not sku or not sku.strip():
            sku = generate_sku(category_code=cat.name[:3].upper(), product_name=name)
            # Ensure uniqueness in case of collision
            counter = 1
            base_generated = sku
            while Product.query.filter_by(sku=sku).first() or ProductVariant.query.filter_by(sku=sku).first():
                sku = f"{base_generated}-{counter:02d}"
                counter += 1
        else:
            sku = validate_product_sku(sku)

        base_price = validate_price(base_price, "Base Price")
        cost_price = validate_price(cost_price or Decimal("0.00"), "Cost Price")
        display_order = max(0, int(display_order or 0))

        slug = slugify(name)
        # Ensure unique slug
        if Product.query.filter_by(slug=slug).first():
            slug = f"{slug}-{sku.lower()}"

        product = Product(
            name=name,
            slug=slug,
            category_id=cat.id,
            sku=sku,
            base_price=base_price,
            cost_price=cost_price,
            description=description.strip() if description else "",
            image_url=image_url.strip() if image_url else None,
            is_available=bool(is_available),
            is_active=bool(is_active),
            display_order=display_order
        )
        db.session.add(product)
        db.session.flush()

        # Handle variants if provided
        if variants_data and isinstance(variants_data, list):
            for v_idx, v_data in enumerate(variants_data):
                v_name = v_data.get("name", "").strip()
                if not v_name:
                    continue
                v_price = validate_price(v_data.get("price", base_price), f"Variant '{v_name}' Price")
                v_cost = validate_price(v_data.get("cost_price", cost_price), f"Variant '{v_name}' Cost")
                v_sku = v_data.get("sku", "").strip().upper()
                if not v_sku:
                    v_sku = f"{product.sku}-V{v_idx + 1:02d}"
                v_sku = validate_variant_sku(v_sku)

                variant = ProductVariant(
                    product_id=product.id,
                    name=v_name,
                    sku=v_sku,
                    price=v_price,
                    cost_price=v_cost,
                    is_available=v_data.get("is_available", True),
                    is_active=True,
                    display_order=v_idx
                )
                db.session.add(variant)

        db.session.commit()
        return product

    @staticmethod
    def update_product(product_id, **kwargs):
        product = CatalogService.get_product_by_id(product_id)

        if "name" in kwargs and kwargs["name"]:
            name = kwargs["name"].strip()
            if name != product.name:
                product.name = name
                # update slug
                new_slug = slugify(name)
                product.slug = new_slug

        if "category_id" in kwargs and kwargs["category_id"]:
            cat_id = int(kwargs["category_id"])
            if cat_id != product.category_id:
                CatalogService.get_category_by_id(cat_id)  # verify existence
                product.category_id = cat_id

        if "sku" in kwargs and kwargs["sku"]:
            new_sku = kwargs["sku"].strip().upper()
            if new_sku != product.sku:
                validate_product_sku(new_sku, exclude_id=product.id)
                product.sku = new_sku

        if "base_price" in kwargs and kwargs["base_price"] is not None:
            product.base_price = validate_price(kwargs["base_price"], "Base Price")

        if "cost_price" in kwargs and kwargs["cost_price"] is not None:
            product.cost_price = validate_price(kwargs["cost_price"], "Cost Price")

        if "description" in kwargs and kwargs["description"] is not None:
            product.description = kwargs["description"].strip()

        if "image_url" in kwargs:
            product.image_url = kwargs["image_url"].strip() if kwargs["image_url"] else None

        if "is_available" in kwargs and kwargs["is_available"] is not None:
            product.is_available = bool(kwargs["is_available"])

        if "is_active" in kwargs and kwargs["is_active"] is not None:
            product.is_active = bool(kwargs["is_active"])

        if "display_order" in kwargs and kwargs["display_order"] is not None:
            product.display_order = max(0, int(kwargs["display_order"]))

        product.updated_at = datetime.utcnow()
        db.session.commit()
        return product

    @staticmethod
    def toggle_availability(product_id):
        product = CatalogService.get_product_by_id(product_id)
        product.is_available = not product.is_available
        product.updated_at = datetime.utcnow()
        db.session.commit()
        return product

    @staticmethod
    def toggle_active(product_id):
        product = CatalogService.get_product_by_id(product_id)
        product.is_active = not product.is_active
        product.updated_at = datetime.utcnow()
        db.session.commit()
        return product

    @staticmethod
    def create_variant(product_id, name, price, sku=None, cost_price=0.0, is_available=True, display_order=0):
        product = CatalogService.get_product_by_id(product_id)
        if not name or not name.strip():
            raise ValidationError("Variant name is required.")
        name = name.strip()

        if not sku or not sku.strip():
            v_count = product.variants.count() + 1
            sku = f"{product.sku}-V{v_count:02d}"
        sku = validate_variant_sku(sku)

        price = validate_price(price, "Variant Price")
        cost_price = validate_price(cost_price or Decimal("0.00"), "Variant Cost Price")

        variant = ProductVariant(
            product_id=product.id,
            name=name,
            sku=sku,
            price=price,
            cost_price=cost_price,
            is_available=bool(is_available),
            is_active=True,
            display_order=max(0, int(display_order or 0))
        )
        db.session.add(variant)
        db.session.commit()
        return variant

    @staticmethod
    def update_variant(variant_id, **kwargs):
        variant = db.session.get(ProductVariant, variant_id)
        if not variant:
            raise NotFoundError("Product variant not found.")

        if "name" in kwargs and kwargs["name"]:
            variant.name = kwargs["name"].strip()

        if "sku" in kwargs and kwargs["sku"]:
            new_sku = kwargs["sku"].strip().upper()
            if new_sku != variant.sku:
                validate_variant_sku(new_sku, exclude_variant_id=variant.id)
                variant.sku = new_sku

        if "price" in kwargs and kwargs["price"] is not None:
            variant.price = validate_price(kwargs["price"], "Variant Price")

        if "cost_price" in kwargs and kwargs["cost_price"] is not None:
            variant.cost_price = validate_price(kwargs["cost_price"], "Variant Cost Price")

        if "is_available" in kwargs and kwargs["is_available"] is not None:
            variant.is_available = bool(kwargs["is_available"])

        if "is_active" in kwargs and kwargs["is_active"] is not None:
            variant.is_active = bool(kwargs["is_active"])

        if "display_order" in kwargs and kwargs["display_order"] is not None:
            variant.display_order = max(0, int(kwargs["display_order"]))

        variant.updated_at = datetime.utcnow()
        db.session.commit()
        return variant

    @staticmethod
    def delete_variant(variant_id):
        variant = db.session.get(ProductVariant, variant_id)
        if not variant:
            raise NotFoundError("Product variant not found.")
        db.session.delete(variant)
        db.session.commit()

    @staticmethod
    def get_catalog_stats():
        total_products = Product.query.filter_by(is_active=True).count()
        available_products = Product.query.filter_by(is_active=True, is_available=True).count()
        total_categories = Category.query.filter_by(is_active=True).count()
        unavailable_products = total_products - available_products
        return {
            "total_products": total_products,
            "available_products": available_products,
            "total_categories": total_categories,
            "unavailable_products": unavailable_products
        }

    @staticmethod
    def get_option_groups(active_only=True):
        query = ProductOptionGroup.query.order_by(ProductOptionGroup.display_order.asc(), ProductOptionGroup.name.asc())
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()
