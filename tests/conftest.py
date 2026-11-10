import sys
import os
from decimal import Decimal
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import create_app
from app.extensions import db
from app.modules.users.models import User
from app.core.permissions import Roles


@pytest.fixture(scope="session")
def app():
    _app = create_app("testing")
    with _app.app_context():
        db.create_all()
        yield _app
        db.drop_all()


@pytest.fixture(autouse=True)
def app_context(app):
    """Keep single app context active across fixtures and test execution."""
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield
        db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def owner_user():
    user = User(
        username="test_owner",
        email="owner@test.local",
        first_name="Test",
        last_name="Owner",
        role=Roles.OWNER,
        is_active=True
    )
    user.set_password("Owner123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def manager_user():
    user = User(
        username="test_manager",
        email="manager@test.local",
        first_name="Test",
        last_name="Manager",
        role=Roles.MANAGER,
        is_active=True
    )
    user.set_password("Manager123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def cashier_user():
    user = User(
        username="test_cashier",
        email="cashier@test.local",
        first_name="Test",
        last_name="Cashier",
        role=Roles.CASHIER,
        is_active=True
    )
    user.set_password("Cashier123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def barista_user():
    user = User(
        username="test_barista",
        email="barista@test.local",
        first_name="Test",
        last_name="Barista",
        role=Roles.BARISTA,
        is_active=True
    )
    user.set_password("Barista123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def staff_user():
    user = User(
        username="test_staff",
        email="staff@test.local",
        first_name="Test",
        last_name="Staff",
        role=Roles.STAFF,
        is_active=True
    )
    user.set_password("Staff123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def inactive_user():
    user = User(
        username="test_inactive",
        email="inactive@test.local",
        first_name="Test",
        last_name="Inactive",
        role=Roles.STAFF,
        is_active=False
    )
    user.set_password("Inactive123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_catalog(app):
    from app.modules.catalog.models import Category, Product, ProductVariant
    from app.modules.inventory.models import Ingredient
    from app.modules.recipes.models import Recipe, RecipeItem

    cat = Category(name="Coffee Drinks", slug="coffee-drinks", description="Signature coffees", is_active=True)
    db.session.add(cat)
    db.session.flush()

    prod = Product(
        name="Vanilla Latte",
        slug="vanilla-latte",
        sku="COF-LAT-001",
        category_id=cat.id,
        base_price=Decimal("5.00"),
        cost_price=Decimal("0.94"),
        is_available=True,
        is_active=True
    )
    db.session.add(prod)
    db.session.flush()

    v1 = ProductVariant(
        product_id=prod.id,
        name="12oz Hot",
        sku="COF-LAT-001-12H",
        price=Decimal("5.00"),
        cost_price=Decimal("0.94"),
        is_available=True,
        is_active=True
    )
    v2 = ProductVariant(
        product_id=prod.id,
        name="16oz Iced",
        sku="COF-LAT-001-16I",
        price=Decimal("6.00"),
        cost_price=Decimal("1.20"),
        is_available=True,
        is_active=True
    )
    db.session.add_all([v1, v2])
    db.session.flush()

    bean = Ingredient(
        name="Test Espresso Beans",
        sku="ING-TEST-BEAN",
        unit="g",
        current_quantity=Decimal("1000.0000"),
        minimum_stock_level=Decimal("100.0000"),
        reorder_level=Decimal("200.0000"),
        cost_per_unit=Decimal("0.0300"),
        is_active=True
    )
    milk = Ingredient(
        name="Test Fresh Milk",
        sku="ING-TEST-MILK",
        unit="ml",
        current_quantity=Decimal("5000.0000"),
        minimum_stock_level=Decimal("500.0000"),
        reorder_level=Decimal("1000.0000"),
        cost_per_unit=Decimal("0.0020"),
        is_active=True
    )
    db.session.add_all([bean, milk])
    db.session.flush()

    recipe = Recipe(product_id=prod.id, instructions="Pull 2 espresso shots, steam 200ml milk.")
    db.session.add(recipe)
    db.session.flush()

    ri1 = RecipeItem(recipe_id=recipe.id, ingredient_id=bean.id, quantity_required=18.0)
    ri2 = RecipeItem(recipe_id=recipe.id, ingredient_id=milk.id, quantity_required=200.0)
    db.session.add_all([ri1, ri2])
    db.session.commit()

    return {"category": cat, "product": prod, "variants": [v1, v2], "recipe": recipe, "ingredients": [bean, milk]}


@pytest.fixture
def sample_inventory(app):
    from app.modules.inventory.models import Supplier, Ingredient, UnitOfMeasure, InventoryCategory
    uom = UnitOfMeasure(code="KG", name="Kilogram", category="WEIGHT", is_active=True)
    icat = InventoryCategory(name="Coffee Beans", code="BEANS", is_active=True)
    sup = Supplier(name="Altitude Roasters", email="orders@altitude.local", is_active=True)
    db.session.add_all([uom, icat, sup])
    db.session.flush()

    item = Ingredient(
        name="Espresso Arabica",
        sku="RAW-ESP-001",
        unit="kg",
        unit_of_measure_id=uom.id,
        category_id=icat.id,
        supplier_id=sup.id,
        current_quantity=Decimal("10.0000"),
        minimum_stock_level=Decimal("2.0000"),
        reorder_level=Decimal("5.0000"),
        cost_per_unit=Decimal("500.0000"),
        is_active=True
    )
    db.session.add(item)
    db.session.commit()
    return {"uom": uom, "category": icat, "supplier": sup, "item": item}
