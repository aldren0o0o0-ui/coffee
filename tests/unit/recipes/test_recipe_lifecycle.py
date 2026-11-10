import pytest
from decimal import Decimal
from app.modules.recipes.services import RecipeService
from app.modules.recipes.units import convert_quantity, are_units_compatible
from app.modules.recipes.models import Recipe, RecipeItem
from app.modules.catalog.models import Product, ProductVariant, Category
from app.modules.inventory.models import Ingredient, StockMovement, StockMovementType
from app.core.exceptions import ValidationError, InsufficientStockError


def test_unit_conversion_math():
    # 1. Same unit
    assert convert_quantity(15.0, "g", "g") == Decimal("15.0000")

    # 2. Weight conversions
    assert convert_quantity(1.5, "kg", "g") == Decimal("1500.0000")
    assert convert_quantity(500, "g", "kg") == Decimal("0.5000")
    assert convert_quantity(1, "oz", "g") == Decimal("28.3495")

    # 3. Volume conversions
    assert convert_quantity(2.0, "l", "ml") == Decimal("2000.0000")
    assert convert_quantity(250, "ml", "l") == Decimal("0.2500")

    # 4. Incompatible units must raise ValidationError
    with pytest.raises(ValidationError):
        convert_quantity(100, "ml", "g")

    with pytest.raises(ValidationError):
        convert_quantity(5, "pcs", "kg")


def test_recipe_creation_and_variant_inheritance(app, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        v1 = sample_catalog["variants"][0]  # 12oz Hot
        v2 = sample_catalog["variants"][1]  # 16oz Iced
        bean = sample_catalog["ingredients"][0]
        milk = sample_catalog["ingredients"][1]

        # 1. Base product recipe
        r_base = RecipeService.save_recipe(
            product_id=prod.id,
            items_data=[
                {"ingredient_id": bean.id, "quantity_required": "18.0", "unit": "g"},
                {"ingredient_id": milk.id, "quantity_required": "200.0", "unit": "ml"}
            ],
            instructions="Pull double shot, steam milk"
        )
        assert r_base.id is not None
        assert r_base.total_cost_decimal == Decimal("0.94")

        # 2. Variant-specific recipe (16oz Iced requires 22g beans and 280ml milk)
        r_v2 = RecipeService.save_recipe(
            product_id=prod.id,
            variant_id=v2.id,
            items_data=[
                {"ingredient_id": bean.id, "quantity_required": "22.0", "unit": "g"},
                {"ingredient_id": milk.id, "quantity_required": "280.0", "unit": "ml"}
            ],
            instructions="Pull double shot, cold milk over ice"
        )
        assert r_v2.id is not None
        # Cost: 22 * 0.03 = 0.66, 280 * 0.002 = 0.56. Total = 1.22
        assert r_v2.total_cost_decimal == Decimal("1.22")

        # 3. Inheritance lookup test:
        # v1 (12oz) has no specific recipe, so it inherits r_base
        lookup_v1 = RecipeService.get_recipe(product_id=prod.id, variant_id=v1.id)
        assert lookup_v1.id == r_base.id
        assert lookup_v1.total_cost_decimal == Decimal("0.94")

        # v2 (16oz) resolves its own specific recipe
        lookup_v2 = RecipeService.get_recipe(product_id=prod.id, variant_id=v2.id)
        assert lookup_v2.id == r_v2.id
        assert lookup_v2.total_cost_decimal == Decimal("1.22")


def test_recipe_validation_rules(app, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        bean = sample_catalog["ingredients"][0]

        # Duplicate ingredients should fail
        with pytest.raises(ValidationError) as exc:
            RecipeService.save_recipe(
                product_id=prod.id,
                items_data=[
                    {"ingredient_id": bean.id, "quantity_required": "10.0", "unit": "g"},
                    {"ingredient_id": bean.id, "quantity_required": "5.0", "unit": "g"}
                ]
            )
        assert "Duplicate ingredient" in str(exc.value)

        # Non-positive quantity should fail
        with pytest.raises(ValidationError) as exc:
            RecipeService.save_recipe(
                product_id=prod.id,
                items_data=[
                    {"ingredient_id": bean.id, "quantity_required": "0.0", "unit": "g"}
                ]
            )
        assert "greater than zero" in str(exc.value)

        # Empty components should fail
        with pytest.raises(ValidationError) as exc:
            RecipeService.save_recipe(
                product_id=prod.id,
                items_data=[]
            )
        assert "at least one" in str(exc.value)


def test_atomic_recipe_consumption_and_insufficient_stock(app, sample_catalog):
    with app.app_context():
        from app.extensions import db
        bean = db.session.get(Ingredient, sample_catalog["ingredients"][0].id)
        milk = db.session.get(Ingredient, sample_catalog["ingredients"][1].id)

        # Setup initial stock
        bean.current_quantity = Decimal("50.0000")
        milk.current_quantity = Decimal("100.0000")
        db.session.commit()

        # Recipe requires 18g beans and 200ml milk
        # If we order quantity = 1:
        # beans (18g <= 50g) OK, but milk (200ml > 100ml) INSUFFICIENT!
        items_reqs = [
            {"ingredient_id": bean.id, "quantity": Decimal("18.0000"), "unit": "g"},
            {"ingredient_id": milk.id, "quantity": Decimal("200.0000"), "unit": "ml"}
        ]

        # Must raise InsufficientStockError
        with pytest.raises(InsufficientStockError) as exc:
            RecipeService.consume_recipe_ingredients(
                items_requirements=items_reqs,
                reference="TEST-FAIL-ORDER"
            )
        assert "Insufficient raw materials" in str(exc.value)
        assert milk.name in str(exc.value)

        # Transaction aborted: rollback session
        db.session.rollback()

        # INVARIANT VERIFICATION: Bean stock must NOT have been deducted!
        reloaded_bean = db.session.get(Ingredient, bean.id)
        reloaded_milk = db.session.get(Ingredient, milk.id)
        assert reloaded_bean.current_quantity == Decimal("50.0000")
        assert reloaded_milk.current_quantity == Decimal("100.0000")

        # Now test successful consumption with sufficient stock
        reloaded_milk.current_quantity = Decimal("500.0000")
        db.session.commit()

        movements = RecipeService.consume_recipe_ingredients(
            items_requirements=items_reqs,
            reference="TEST-SUCCESS-ORDER"
        )
        db.session.commit()

        assert len(movements) == 2
        db.session.expire_all()
        reloaded_bean = db.session.get(Ingredient, bean.id)
        reloaded_milk = db.session.get(Ingredient, milk.id)

        assert reloaded_bean.current_quantity == Decimal("32.0000")   # 50 - 18
        assert reloaded_milk.current_quantity == Decimal("300.0000")  # 500 - 200
