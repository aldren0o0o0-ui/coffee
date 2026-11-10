from decimal import Decimal
import pytest
from app.modules.inventory.services import InventoryService
from app.modules.inventory.models import StockMovementType, PurchaseStatus, Ingredient, StockMovement
from app.core.exceptions import InsufficientStockError, ValidationError, NotFoundError


def test_inventory_item_creation_with_numeric_precision(app, sample_inventory):
    with app.app_context():
        uom = sample_inventory["uom"]
        cat = sample_inventory["category"]
        sup = sample_inventory["supplier"]

        item = InventoryService.create_item(
            name="Matcha Powder Ceremonial",
            sku="RAW-MAT-TEST",
            unit_of_measure_id=uom.id,
            category_id=cat.id,
            initial_quantity=Decimal("5.5000"),
            minimum_stock=Decimal("1.0000"),
            reorder_level=Decimal("2.0000"),
            cost_per_unit=Decimal("4500.0000"),
            supplier_id=sup.id
        )
        assert item.id is not None
        assert item.current_quantity == Decimal("5.5000")
        assert item.minimum_stock_level == Decimal("1.0000")
        assert item.cost_per_unit == Decimal("4500.0000")

        # Verify initial movement was recorded
        mv = StockMovement.query.filter_by(ingredient_id=item.id).first()
        assert mv is not None
        assert mv.movement_type == StockMovementType.INITIAL_STOCK
        assert mv.quantity == Decimal("5.5000")


def test_duplicate_inventory_sku_fails(app, sample_inventory):
    with app.app_context():
        uom = sample_inventory["uom"]
        with pytest.raises(ValidationError) as exc:
            InventoryService.create_item(
                name="Duplicate Item",
                sku="RAW-ESP-001",  # Existing SKU from sample_inventory
                unit_of_measure_id=uom.id
            )
        assert "already in use" in str(exc.value)


def test_stock_adjustment_requires_reason(app, sample_inventory):
    with app.app_context():
        item = sample_inventory["item"]
        with pytest.raises(ValidationError) as exc:
            InventoryService.adjust_stock(
                item_id=item.id,
                quantity=Decimal("2.0000"),
                reason=""  # Missing reason
            )
        assert "reason is mandatory" in str(exc.value)


def test_negative_stock_prevention_on_adjustment(app, sample_inventory):
    with app.app_context():
        item = sample_inventory["item"]  # Current stock is 10.0000
        # Attempt deduction of 15.0000 (would make stock -5.0000)
        with pytest.raises(InsufficientStockError) as exc:
            InventoryService.adjust_stock(
                item_id=item.id,
                quantity=Decimal("-15.0000"),
                reason="Testing overflow deduction"
            )
        assert "Insufficient stock" in str(exc.value)

        # Confirm stock balance remained strictly unchanged
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("10.0000")


def test_stock_adjustment_success(app, sample_inventory):
    with app.app_context():
        item = sample_inventory["item"]  # 10.0000
        # Deduct 2.5 kg
        mv = InventoryService.adjust_stock(
            item_id=item.id,
            quantity=Decimal("-2.5000"),
            reason="Spillage during bean grinding"
        )
        assert mv.movement_type == StockMovementType.ADJUSTMENT_OUT
        assert mv.quantity == Decimal("-2.5000")

        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("7.5000")

        # Add 5.0 kg
        mv2 = InventoryService.adjust_stock(
            item_id=item.id,
            quantity=Decimal("5.0000"),
            reason="Unrecorded delivery addition"
        )
        assert mv2.movement_type == StockMovementType.ADJUSTMENT_IN
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("12.5000")


def test_low_stock_and_out_of_stock_detection(app, sample_inventory):
    with app.app_context():
        item = sample_inventory["item"]  # Current = 10.0000, Reorder = 5.0000
        assert item.is_low_stock is False
        assert item.is_out_of_stock is False
        assert item.stock_status == "IN_STOCK"

        # Reduce to 4.0000 (below reorder_level of 5.0000)
        InventoryService.adjust_stock(item.id, Decimal("-6.0000"), reason="Usage test")
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.is_low_stock is True
        assert reloaded.stock_status == "LOW_STOCK"

        # Reduce to 0.0000 (out of stock)
        InventoryService.adjust_stock(item.id, Decimal("-4.0000"), reason="Exhaustion test")
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.is_out_of_stock is True
        assert reloaded.stock_status == "OUT_OF_STOCK"


def test_supplier_creation_and_validation(app):
    with app.app_context():
        sup = InventoryService.create_supplier(
            name="Organic Dairy Local",
            contact_person="Juan Cruz",
            email="juan@organicdairy.local",
            phone="0917-111-2222"
        )
        assert sup.id is not None
        assert sup.name == "Organic Dairy Local"

        # Invalid email format should raise ValidationError
        with pytest.raises(ValidationError):
            InventoryService.create_supplier(
                name="Another Vendor",
                email="not-an-email"
            )


def test_purchase_order_draft_does_not_affect_stock(app, sample_inventory):
    with app.app_context():
        sup = sample_inventory["supplier"]
        item = sample_inventory["item"]  # Stock = 10.0000

        po = InventoryService.create_purchase(
            supplier_id=sup.id,
            reference_number="PO-TEST-001",
            items_data=[{
                "ingredient_id": item.id,
                "quantity": Decimal("20.0000"),
                "unit_cost": Decimal("480.0000")
            }]
        )
        assert po.id is not None
        assert po.status == PurchaseStatus.DRAFT
        assert po.total_cost == Decimal("9600.00")

        # Stock must NOT have changed yet
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("10.0000")


def test_purchase_order_receiving_increments_stock(app, sample_inventory):
    with app.app_context():
        sup = sample_inventory["supplier"]
        item = sample_inventory["item"]  # Stock = 10.0000

        po = InventoryService.create_purchase(
            supplier_id=sup.id,
            reference_number="PO-TEST-002",
            items_data=[{
                "ingredient_id": item.id,
                "quantity": Decimal("15.0000"),
                "unit_cost": Decimal("490.0000")
            }]
        )

        # Receive stock
        received_po = InventoryService.receive_purchase(po.id)
        assert received_po.status == PurchaseStatus.RECEIVED

        # Stock should now be 10.0000 + 15.0000 = 25.0000
        reloaded = InventoryService.get_item_by_id(item.id)
        assert reloaded.current_quantity == Decimal("25.0000")
        assert reloaded.cost_per_unit == Decimal("490.0000")

        # Stock movement was logged
        movement = StockMovement.query.filter_by(reference="PO-TEST-002").first()
        assert movement is not None
        assert movement.movement_type == StockMovementType.PURCHASE
        assert movement.quantity == Decimal("15.0000")
