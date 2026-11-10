import pytest
from app.modules.pos.services import POSService
from app.modules.pos.models import POSRegisterShift
from app.modules.sales.models import Sale, SaleStatus


def test_pos_shift_lifecycle_and_checkout(app, barista_user, sample_catalog):
    with app.app_context():
        # 1. Open shift
        shift = POSService.open_shift(barista_user.id, opening_cash=100.00)
        assert shift.is_active is True
        assert shift.opening_cash == 100.00

        # 2. Checkout
        prod = sample_catalog["product"]
        sale = POSService.checkout(
            user_id=barista_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method="Cash",
            cash_tendered=10.00,
            tax_rate=0.08
        )
        assert sale.id is not None
        assert sale.status == SaleStatus.COMPLETED
        assert float(sale.total_amount) == 5.40  # 5.00 + 0.40 tax
        assert float(sale.change_due) == 4.60    # 10.00 - 5.40

        # Verify shift updated
        assert shift.total_orders_count == 1
        assert float(shift.total_sales_amount) == 5.40

        # 3. Close shift
        closed_shift = POSService.close_shift(shift.id, closing_cash=105.40)
        assert closed_shift.is_active is False
        assert closed_shift.discrepancy == 0.00
