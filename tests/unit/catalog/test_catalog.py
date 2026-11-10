from decimal import Decimal
import pytest
from app.modules.catalog.services import CatalogService
from app.modules.catalog.models import Category, Product, ProductVariant
from app.core.exceptions import ValidationError, NotFoundError


def test_create_category_and_product(app):
    with app.app_context():
        cat = CatalogService.create_category("Cold Beverages", "Chilled specialty drinks", display_order=2)
        assert cat.id is not None
        assert cat.name == "Cold Beverages"
        assert cat.slug == "cold-beverages"
        assert cat.display_order == 2
        assert cat.is_active is True

        prod = CatalogService.create_product(
            name="Iced Americano",
            category_id=cat.id,
            base_price=Decimal("140.00"),
            cost_price=Decimal("25.00"),
            sku="COLD-AME-01"
        )
        assert prod.id is not None
        assert prod.sku == "COLD-AME-01"
        assert prod.base_price == Decimal("140.00")
        assert prod.cost_price == Decimal("25.00")
        assert prod.is_available is True
        assert prod.is_active is True


def test_duplicate_category_name_fails(app):
    with app.app_context():
        CatalogService.create_category("Bakery", "Baked goods")
        with pytest.raises(ValidationError) as exc:
            CatalogService.create_category("Bakery", "Duplicate")
        assert "already exists" in str(exc.value)


def test_duplicate_product_sku_fails(app, sample_catalog):
    with app.app_context():
        cat = sample_catalog["category"]
        with pytest.raises(ValidationError) as exc:
            CatalogService.create_product(
                name="Another Latte",
                category_id=cat.id,
                base_price=Decimal("150.00"),
                sku="COF-LAT-001"  # Existing SKU
            )
        assert "already in use" in str(exc.value)


def test_product_variants_creation_and_uniqueness(app, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        v = CatalogService.create_variant(
            product_id=prod.id,
            name="20oz Extra Large",
            price=Decimal("200.00"),
            sku="COF-LAT-001-20"
        )
        assert v.id is not None
        assert v.price == Decimal("200.00")
        assert v.sku == "COF-LAT-001-20"

        # Duplicate variant SKU should fail
        with pytest.raises(ValidationError):
            CatalogService.create_variant(
                product_id=prod.id,
                name="Duplicate SKU Variant",
                price=Decimal("210.00"),
                sku="COF-LAT-001-20"
            )


def test_toggle_product_availability(app, sample_catalog):
    with app.app_context():
        prod_id = sample_catalog["product"].id
        toggled = CatalogService.toggle_availability(prod_id)
        assert toggled.is_available is False
        toggled = CatalogService.toggle_availability(prod_id)
        assert toggled.is_available is True


def test_toggle_product_active_state(app, sample_catalog):
    with app.app_context():
        prod_id = sample_catalog["product"].id
        toggled = CatalogService.toggle_active(prod_id)
        assert toggled.is_active is False
        toggled = CatalogService.toggle_active(prod_id)
        assert toggled.is_active is True


def test_price_negative_validation(app, sample_catalog):
    with app.app_context():
        cat = sample_catalog["category"]
        with pytest.raises(ValidationError):
            CatalogService.create_product(
                name="Negative Price Item",
                category_id=cat.id,
                base_price=Decimal("-10.00")
            )


def test_category_safe_deletion_guard(app, sample_catalog):
    with app.app_context():
        cat = sample_catalog["category"]
        # Category contains an active product, deletion should be blocked
        with pytest.raises(ValidationError) as exc:
            CatalogService.delete_category(cat.id)
        assert "contains" in str(exc.value)


def test_catalog_stats_calculation(app, sample_catalog):
    with app.app_context():
        stats = CatalogService.get_catalog_stats()
        assert stats["total_products"] >= 1
        assert stats["available_products"] >= 1
        assert stats["total_categories"] >= 1
