import pytest
from decimal import Decimal
from app.modules.pos.services import POSService
from app.modules.pos.models import POSRegisterShift
from app.modules.sales.models import Sale, SaleStatus, PaymentMethod
from app.modules.catalog.models import ProductOptionGroup, ProductOption
from app.core.exceptions import ValidationError, NotFoundError
from app.extensions import db


def test_pos_shift_lifecycle_and_discrepancy(app, cashier_user):
    with app.app_context():
        # 1. Open shift with $120.00 float
        shift = POSService.open_shift(cashier_user.id, opening_cash=Decimal("120.00"), notes="Morning Shift")
        assert shift.id is not None
        assert shift.is_active is True
        assert Decimal(str(shift.opening_cash)) == Decimal("120.00")

        # 2. Cannot open a second concurrent shift for same cashier
        with pytest.raises(ValidationError) as exc:
            POSService.open_shift(cashier_user.id, opening_cash=50.00)
        assert "already have an active register shift" in str(exc.value)

        # 3. Close shift with cash shortage ($115.00 counted, expected $120.00)
        closed_short = POSService.close_shift(shift.id, closing_cash=Decimal("115.00"), notes="Short $5")
        assert closed_short.is_active is False
        assert closed_short.discrepancy == -5.00

        # 4. Closing an already closed shift fails
        with pytest.raises(NotFoundError):
            POSService.close_shift(shift.id, closing_cash=120.00)


def test_server_authoritative_variant_and_modifier_pricing(app, cashier_user, sample_catalog):
    with app.app_context():
        prod = db.session.get(type(sample_catalog["product"]), sample_catalog["product"].id)
        v2 = db.session.get(type(sample_catalog["variants"][1]), sample_catalog["variants"][1].id)  # 16oz Iced: $6.00

        # Create modifier group and options
        group = ProductOptionGroup(name="Milk Options", is_active=True)
        db.session.add(group)
        db.session.flush()

        opt_oat = ProductOption(group_id=group.id, name="Oat Milk", price_adjustment=Decimal("0.80"), is_available=True)
        opt_shot = ProductOption(group_id=group.id, name="Extra Shot", price_adjustment=Decimal("1.25"), is_available=True)
        db.session.add_all([opt_oat, opt_shot])
        db.session.commit()

        # Checkout with variant and 2 modifiers:
        # Base variant = $6.00 + $0.80 (Oat) + $1.25 (Shot) = $8.05 unit price
        # Quantity = 2 -> Subtotal = $16.10
        # Tax (8%) = 16.10 * 0.08 = 1.288 -> $1.29
        # Total = $17.39
        # Client attempts price tampering by passing $1.00 in payload
        items_data = [{
            "product_id": prod.id,
            "variant_id": v2.id,
            "options": [{"id": opt_oat.id}, {"id": opt_shot.id}],
            "quantity": 2,
            "client_price": 1.00,  # Fraudulent price injection
            "subtotal": 2.00
        }]

        sale = POSService.checkout(
            user_id=cashier_user.id,
            items_data=items_data,
            payment_method=PaymentMethod.CARD,
            tax_rate=0.08
        )

        assert sale.subtotal_amount == Decimal("16.10")
        assert sale.tax_amount == Decimal("1.29")
        assert sale.total_amount == Decimal("17.39")

        # Verify sale item details
        assert len(sale.items) == 1
        item = sale.items[0]
        assert item.variant_id == v2.id
        assert item.variant_name == v2.name
        assert item.unit_price == Decimal("8.05")
        assert len(item.options_data) == 2


def test_cash_tendered_and_change_validation(app, cashier_user, sample_catalog):
    with app.app_context():
        prod = db.session.get(type(sample_catalog["product"]), sample_catalog["product"].id)  # $5.00

        # Subtotal = $5.00, Tax (8%) = $0.40 -> Total = $5.40
        # 1. Tendered less than total -> ValidationError
        with pytest.raises(ValidationError) as exc:
            POSService.checkout(
                user_id=cashier_user.id,
                items_data=[{"product_id": prod.id, "quantity": 1}],
                payment_method=PaymentMethod.CASH,
                cash_tendered=Decimal("5.00"),
                tax_rate=0.08
            )
        assert "less than total amount" in str(exc.value)

        # 2. Tendered exact amount ($5.40) -> change $0.00
        sale_exact = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=Decimal("5.40"),
            tax_rate=0.08
        )
        assert sale_exact.change_due == Decimal("0.00")

        # 3. Tendered $10.00 bill -> change $4.60
        sale_change = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=Decimal("10.00"),
            tax_rate=0.08
        )
        assert sale_change.change_due == Decimal("4.60")
