import pytest
from decimal import Decimal
from app.modules.pos.services import POSService
from app.modules.recipes.services import RecipeService
from app.modules.pos.models import POSRegisterShift
from app.modules.sales.models import Sale, SaleItem, SaleStatus, PaymentMethod
from app.modules.inventory.models import Ingredient, StockMovement, StockMovementType
from app.modules.recipes.models import Recipe, RecipeItem
from app.core.exceptions import InsufficientStockError
from app.extensions import db


def test_pos_e2e_atomic_checkout_success(app, cashier_user, sample_catalog):
    with app.app_context():
        # 1. Cashier opens shift
        shift = POSService.open_shift(cashier_user.id, opening_cash=Decimal("150.00"))
        assert shift.is_active is True

        prod = db.session.get(type(sample_catalog["product"]), sample_catalog["product"].id)
        v1 = db.session.get(type(sample_catalog["variants"][0]), sample_catalog["variants"][0].id)
        bean = db.session.get(Ingredient, sample_catalog["ingredients"][0].id)
        milk = db.session.get(Ingredient, sample_catalog["ingredients"][1].id)

        # Baseline inventory: bean=1000g, milk=5000ml
        bean.current_quantity = Decimal("1000.0000")
        milk.current_quantity = Decimal("5000.0000")
        db.session.commit()

        initial_movements_count = StockMovement.query.count()

        # 2. Checkout 2x of Vanilla Latte (Base recipe: 18g bean, 200ml milk per unit)
        # Total deduction: 36g bean, 400ml milk
        sale = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "variant_id": v1.id, "quantity": 2}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=Decimal("15.00"),
            customer_name="Alice",
            tax_rate=0.08
        )

        assert sale.id is not None
        assert sale.customer_name == "Alice"
        assert sale.status == SaleStatus.COMPLETED
        assert sale.shift_id == shift.id
        assert sale.total_amount == Decimal("10.80")  # (5.00 * 2) * 1.08 = 10.80
        assert sale.change_due == Decimal("4.20")    # 15.00 - 10.80

        # 3. Verify exact inventory deductions
        reloaded_bean = db.session.get(Ingredient, bean.id)
        reloaded_milk = db.session.get(Ingredient, milk.id)
        assert reloaded_bean.current_quantity == Decimal("964.0000")  # 1000 - 36
        assert reloaded_milk.current_quantity == Decimal("4600.0000") # 5000 - 400

        # Verify StockMovement entries logged
        new_movements = StockMovement.query.filter_by(reference=f"Sale #{sale.invoice_no}").all()
        assert len(new_movements) == 2
        for m in new_movements:
            assert m.movement_type == StockMovementType.CONSUMPTION
            assert m.quantity < 0

        # 4. Verify shift updated
        assert shift.total_orders_count == 1
        assert shift.total_sales_amount == Decimal("10.80")

        # 5. Close shift with exact cash: opening $150 + cash sales $10.80 = $160.80
        closed_shift = POSService.close_shift(shift.id, closing_cash=Decimal("160.80"))
        assert closed_shift.is_active is False
        assert closed_shift.discrepancy == 0.00


def test_pos_atomic_rollback_on_insufficient_ingredient(app, cashier_user, sample_catalog):
    """
    CRITICAL ATOMIC INVENTORY DEDUCTION CONTRACT:
    When any raw material in the cart has insufficient stock:
    - Entire transaction aborts with InsufficientStockError.
    - Zero sales are persisted.
    - Zero stock movements are logged.
    - Zero stock is deducted from ANY ingredient (all or nothing).
    """
    with app.app_context():
        prod = db.session.get(type(sample_catalog["product"]), sample_catalog["product"].id)
        bean = db.session.get(Ingredient, sample_catalog["ingredients"][0].id)
        milk = db.session.get(Ingredient, sample_catalog["ingredients"][1].id)

        # Sufficient beans (500g), but milk has only 50ml (needs 200ml per latte)
        bean.current_quantity = Decimal("500.0000")
        milk.current_quantity = Decimal("50.0000")
        db.session.commit()

        initial_sales_count = Sale.query.count()
        initial_movements_count = StockMovement.query.count()

        # Attempt to checkout
        with pytest.raises(InsufficientStockError) as exc:
            POSService.checkout(
                user_id=cashier_user.id,
                items_data=[{"product_id": prod.id, "quantity": 1}],
                payment_method=PaymentMethod.CASH,
                cash_tendered=Decimal("10.00")
            )

        assert "Insufficient raw materials" in str(exc.value)
        assert milk.name in str(exc.value)

        # VERIFY INVARIANTS:
        # 1. Zero sales created
        assert Sale.query.count() == initial_sales_count

        # 2. Zero stock movements created
        assert StockMovement.query.count() == initial_movements_count

        # 3. Beans were NOT partially consumed!
        reloaded_bean = db.session.get(Ingredient, bean.id)
        reloaded_milk = db.session.get(Ingredient, milk.id)
        assert reloaded_bean.current_quantity == Decimal("500.0000")
        assert reloaded_milk.current_quantity == Decimal("50.0000")


def test_pos_idempotent_duplicate_checkout(app, cashier_user, sample_catalog):
    """Verify duplicate checkout submissions return the existing sale without double deducting stock."""
    with app.app_context():
        prod = db.session.get(type(sample_catalog["product"]), sample_catalog["product"].id)
        bean = db.session.get(Ingredient, sample_catalog["ingredients"][0].id)
        milk = db.session.get(Ingredient, sample_catalog["ingredients"][1].id)

        bean.current_quantity = Decimal("500.0000")
        milk.current_quantity = Decimal("2000.0000")
        db.session.commit()

        idempotency_key = "idemp_test_key_abc_999"

        # 1. First checkout call
        sale1 = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CARD,
            idempotency_key=idempotency_key
        )
        assert sale1.id is not None
        assert sale1.idempotency_key == idempotency_key

        reloaded_bean = db.session.get(Ingredient, bean.id)
        # Deducted 18g beans: 500 - 18 = 482
        assert reloaded_bean.current_quantity == Decimal("482.0000")

        # 2. Second checkout call with same idempotency key (e.g. cashier double-click or network retry)
        sale2 = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CARD,
            idempotency_key=idempotency_key
        )

        # Must return the EXACT SAME sale record
        assert sale2.id == sale1.id
        assert sale2.invoice_no == sale1.invoice_no

        # Must NOT have deducted stock a second time!
        reloaded_bean_after = db.session.get(Ingredient, bean.id)
        assert reloaded_bean_after.current_quantity == Decimal("482.0000")
