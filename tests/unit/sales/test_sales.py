import pytest
from app.modules.sales.services import SalesService
from app.modules.sales.models import Sale, SaleStatus
from app.core.exceptions import ValidationError


def test_sales_refund(app, barista_user, sample_catalog):
    with app.app_context():
        from app.modules.pos.services import POSService
        prod = sample_catalog["product"]
        sale = POSService.checkout(
            user_id=barista_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method="Card",
            tax_rate=0.08
        )
        assert sale.status == SaleStatus.COMPLETED

        refunded = SalesService.refund_sale(sale.id, reason="Customer canceled", user_id=barista_user.id)
        assert refunded.status == SaleStatus.REFUNDED

        # Double refund should fail
        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, reason="Double refund attempt")
