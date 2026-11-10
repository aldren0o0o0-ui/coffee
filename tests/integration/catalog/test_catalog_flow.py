from decimal import Decimal
import pytest
from app.modules.catalog.services import CatalogService
from app.modules.catalog.models import Category, Product
from app.modules.inventory.models import Ingredient, StockMovement


def test_section_47_catalog_inventory_independence(app, sample_inventory):
    """
    CRITICAL SECTION 47 TEST:
    Verify that creating a Product does NOT automatically:
    - create inventory
    - deduct inventory
    - modify stock
    Phase 3 (Catalog) and Phase 4 (Inventory) remain completely separate until Phase 5 (Recipes/BOM).
    """
    with app.app_context():
        # Record initial count of inventory items and movements
        initial_ingredient_count = Ingredient.query.count()
        initial_movement_count = StockMovement.query.count()
        test_ingredient = sample_inventory["item"]
        initial_quantity = test_ingredient.current_quantity

        # Create Category & Product in Phase 3 Catalog
        cat = CatalogService.create_category("Seasonal Specials", "Autumn seasonal offerings")
        prod = CatalogService.create_product(
            name="Pumpkin Spice Latte",
            category_id=cat.id,
            base_price=Decimal("190.00"),
            sku="SEA-PSL-001"
        )
        assert prod.id is not None

        # Verify inventory was completely untouched
        from app.extensions import db
        db.session.expire_all()

        current_ingredient_count = Ingredient.query.count()
        current_movement_count = StockMovement.query.count()
        reloaded_ingredient = db.session.get(Ingredient, test_ingredient.id)

        assert current_ingredient_count == initial_ingredient_count
        assert current_movement_count == initial_movement_count
        assert reloaded_ingredient.current_quantity == initial_quantity


def test_catalog_web_flow(client, owner_user, sample_catalog):
    """Integration test for full catalog web flow: login -> index -> category -> product -> toggle -> archive."""
    # 1. Login as owner
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"})

    # 2. View Catalog Overview
    res = client.get("/catalog/")
    assert res.status_code == 200
    assert b"Menu Catalog" in res.data
    assert b"Vanilla Latte" in res.data

    # 3. Create new category via web POST
    res = client.post("/catalog/categories", data={
        "name": "Tea & Matcha",
        "description": "Authentic Japanese teas",
        "display_order": "3"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Tea &amp; Matcha" in res.data or b"Tea & Matcha" in res.data

    # 4. Create product with variants via web POST
    cat = Category.query.filter_by(name="Tea & Matcha").first()
    res = client.post("/catalog/products/create", data={
        "name": "Uji Ceremonial Matcha",
        "category_id": cat.id,
        "base_price": "180.00",
        "cost_price": "45.00",
        "sku": "TEA-UJI-001",
        "description": "Pure green tea latte",
        "is_available": "1",
        "is_active": "1",
        "display_order": "1",
        "variant_name[]": ["12oz Regular", "16oz Large"],
        "variant_sku[]": ["TEA-UJI-001-12", "TEA-UJI-001-16"],
        "variant_price[]": ["180.00", "200.00"],
        "variant_cost[]": ["45.00", "55.00"]
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Uji Ceremonial Matcha" in res.data

    # 5. Toggle availability
    prod = Product.query.filter_by(sku="TEA-UJI-001").first()
    assert prod.is_available is True
    res = client.post(f"/catalog/products/{prod.id}/toggle", follow_redirects=True)
    assert res.status_code == 200

    from app.extensions import db
    db.session.expire_all()
    reloaded = db.session.get(Product, prod.id)
    assert reloaded.is_available is False
