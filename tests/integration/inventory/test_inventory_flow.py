from decimal import Decimal
import pytest
from app.modules.inventory.services import InventoryService
from app.modules.inventory.models import Ingredient, StockMovement, StockMovementType, UnitOfMeasure, Supplier, InventoryCategory
from app.core.exceptions import InsufficientStockError


def test_section_46_critical_end_to_end_inventory_workflow(app):
    """
    CRITICAL SECTION 46 TEST:
    Initial Stock: 0 kg
    Receive: 10 kg @ ₱500/kg -> current_quantity = 10 kg, Stock Movement: PURCHASE / +10 kg
    Then adjust: -2 kg -> current_quantity = 8 kg, Stock Movement: ADJUSTMENT_OUT / -2 kg
    Then attempt: -9 kg -> Operation rejected (InsufficientStockError), current_quantity remains 8 kg, no invalid movement created.
    """
    with app.app_context():
        # Setup UOM, category, and supplier
        uom = UnitOfMeasure(code="KG", name="Kilogram", category="WEIGHT", is_active=True)
        cat = InventoryCategory(name="Raw Beans", code="RBEANS", is_active=True)
        sup = Supplier(name="Specialty Coffee Trader", is_active=True)
        from app.extensions import db
        db.session.add_all([uom, cat, sup])
        db.session.flush()

        # Step 1: Initial Stock = 0 kg
        item = InventoryService.create_item(
            name="Ethiopian Yirgacheffe Beans",
            sku="RAW-YIRG-01",
            unit_of_measure_id=uom.id,
            category_id=cat.id,
            supplier_id=sup.id,
            initial_quantity=Decimal("0.0000"),
            cost_per_unit=Decimal("500.0000")
        )
        assert item.current_quantity == Decimal("0.0000")
        assert StockMovement.query.filter_by(ingredient_id=item.id).count() == 0

        # Step 2: Receive 10 kg @ ₱500/kg
        po = InventoryService.create_purchase(
            supplier_id=sup.id,
            reference_number="PO-YIRG-001",
            items_data=[{
                "ingredient_id": item.id,
                "quantity": Decimal("10.0000"),
                "unit_cost": Decimal("500.0000")
            }]
        )
        InventoryService.receive_purchase(po.id)

        # Expected: current_quantity = 10 kg
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("10.0000")

        # Expected: Stock Movement: PURCHASE / +10 kg
        movements = StockMovement.query.filter_by(ingredient_id=item.id).all()
        assert len(movements) == 1
        assert movements[0].movement_type == StockMovementType.PURCHASE
        assert movements[0].quantity == Decimal("10.0000")
        assert movements[0].unit_cost == Decimal("500.0000")

        # Step 3: Then adjust: -2 kg
        adj_mv = InventoryService.adjust_stock(
            item_id=item.id,
            quantity=Decimal("-2.0000"),
            reason="Damaged / spilled beans"
        )
        assert adj_mv.movement_type == StockMovementType.ADJUSTMENT_OUT
        assert adj_mv.quantity == Decimal("-2.0000")

        # Expected: current_quantity = 8 kg
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("8.0000")

        movements = StockMovement.query.filter_by(ingredient_id=item.id).all()
        assert len(movements) == 2

        # Step 4: Then attempt deduction of -9 kg
        with pytest.raises(InsufficientStockError):
            InventoryService.adjust_stock(
                item_id=item.id,
                quantity=Decimal("-9.0000"),
                reason="Attempting to deduct more than on-hand stock"
            )

        # Expected: operation rejected, current_quantity remains 8 kg, no invalid movement created
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("8.0000")

        movements = StockMovement.query.filter_by(ingredient_id=item.id).all()
        assert len(movements) == 2  # Still exactly 2 movements!


def test_inventory_web_flow(client, owner_user, sample_inventory):
    """Integration test for full web flow: login -> dashboard -> view items -> adjust -> purchases."""
    # 1. Login as owner
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"})

    # 2. View Inventory Dashboard
    res = client.get("/inventory/")
    assert res.status_code == 200
    assert b"Inventory & Stock Overview" in res.data or b"Inventory" in res.data

    # 3. View Inventory Items list
    res = client.get("/inventory/items")
    assert res.status_code == 200
    assert b"Espresso Arabica" in res.data

    # 4. Perform stock adjustment via web POST
    item = sample_inventory["item"]
    res = client.post("/inventory/adjust", data={
        "ingredient_id": item.id,
        "quantity": "5.0",
        "reason": "Shipment arrived directly",
        "notes": "Web flow test"
    }, follow_redirects=True)
    assert res.status_code == 200

    # Verify updated stock
    from app.extensions import db
    db.session.expire_all()
    reloaded = db.session.get(Ingredient, item.id)
    assert reloaded.current_quantity == Decimal("15.0000")

    # 5. Create Supplier via web POST
    res = client.post("/inventory/suppliers", data={
        "name": "Pacific Cups Co",
        "contact_person": "Alex Vance",
        "email": "alex@pacificcups.local",
        "phone": "555-9000",
        "address": "San Francisco, CA"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Pacific Cups Co" in res.data
