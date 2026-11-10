import pytest
from app.modules.recipes.services import RecipeService
from app.modules.catalog.models import Product
from app.modules.inventory.models import Ingredient


def test_recipe_cost_and_deduction(app, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        recipe = sample_catalog["recipe"]

        # Cost: 18g * 0.03 + 200ml * 0.002 = 0.54 + 0.40 = 0.94
        assert recipe.total_cost == 0.94

        avail, missing = RecipeService.check_stock_availability(prod.id, order_quantity=2)
        assert avail is True
        assert len(missing) == 0

        # Simulate sale deduction
        bean = sample_catalog["ingredients"][0]
        initial_bean_stock = bean.current_stock
        RecipeService.deduct_inventory_for_sale_item(prod.id, order_quantity=2)
        from app.modules.inventory.services import InventoryService
        updated_bean = InventoryService.get_ingredient_by_id(bean.id)
        assert updated_bean.current_stock == initial_bean_stock - 36.0
