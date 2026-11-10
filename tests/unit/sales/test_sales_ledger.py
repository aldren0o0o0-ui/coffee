import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from app.extensions import db
from app.modules.pos.services import POSService
from app.modules.sales.services import SalesService
from app.modules.sales.models import Sale, SaleStatus, Payment, PaymentStatus, PaymentMethod
from app.core.exceptions import ValidationError, NotFoundError
from app.modules.auth.models import AuditLog


def test_payment_record_created_on_checkout(app, cashier_user, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        sale = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 2}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=15.00
        )
        assert sale.id is not None
        assert len(sale.payments) == 1
        p = sale.payments[0]
        assert p.payment_method == PaymentMethod.CASH
        assert p.amount == sale.total_amount
        assert p.status == PaymentStatus.SUCCESS
        assert p.cash_tendered == Decimal("15.00")
        assert p.change_due == Decimal("15.00") - sale.total_amount


def test_sales_summary_calculations(app, cashier_user, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        # Sale 1: Cash $5.40 (assuming 5.00 + 8% tax)
        sale1 = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=10.00
        )
        # Sale 2: Card
        sale2 = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CARD
        )

        summary = SalesService.get_sales_summary()
        expected_gross = sale1.total_amount + sale2.total_amount
        assert summary["gross_sales"] == expected_gross
        assert summary["refund_amount"] == Decimal("0.00")
        assert summary["net_sales"] == expected_gross
        assert summary["transaction_count"] == 2
        assert summary["completed_count"] == 2
        assert summary["cash_sales"] == sale1.total_amount
        assert summary["non_cash_sales"] == sale2.total_amount

        # Process a partial refund on sale1
        SalesService.refund_sale(sale1.id, refund_amount=Decimal("2.00"), reason="Partial dissatisfaction", user_id=cashier_user.id)
        summary_after_refund = SalesService.get_sales_summary()
        assert summary_after_refund["refund_amount"] == Decimal("2.00")
        assert summary_after_refund["net_sales"] == expected_gross - Decimal("2.00")


def test_void_sale_lifecycle_and_shift_adjustment(app, manager_user, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        # Open shift
        shift = POSService.open_shift(user_id=manager_user.id, opening_cash=100.00)

        sale = POSService.checkout(
            user_id=manager_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=20.00
        )
        assert shift.total_sales_amount == sale.total_amount
        assert shift.total_orders_count == 1

        # Void sale
        voided = SalesService.void_sale(sale.id, reason="Customer walked away", user_id=manager_user.id)
        assert voided.status == SaleStatus.VOIDED
        assert voided.payment_status == PaymentStatus.VOIDED
        assert voided.void_reason == "Customer walked away"
        assert voided.voided_at is not None
        assert voided.voided_by_id == manager_user.id
        assert voided.net_amount == Decimal("0.00")

        # Shift sales deducted
        assert shift.total_sales_amount == Decimal("0.00")
        assert shift.total_orders_count == 0

        # Payments marked voided
        for p in voided.payments:
            assert p.status == PaymentStatus.VOIDED

        # Cannot void again
        with pytest.raises(ValidationError):
            SalesService.void_sale(sale.id, reason="Try void again", user_id=manager_user.id)

        # Cannot refund a voided sale
        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, reason="Try refund voided", user_id=manager_user.id)


def test_refund_sale_lifecycle_and_validation(app, manager_user, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        sale = POSService.checkout(
            user_id=manager_user.id,
            items_data=[{"product_id": prod.id, "quantity": 2}],
            payment_method=PaymentMethod.CARD
        )
        total = sale.total_amount

        # Cannot refund with <= 0
        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, refund_amount=Decimal("0.00"), user_id=manager_user.id)

        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, refund_amount=Decimal("-5.00"), user_id=manager_user.id)

        # Cannot refund amount exceeding balance
        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, refund_amount=total + Decimal("1.00"), user_id=manager_user.id)

        # Partial refund
        part_amt = Decimal("3.00")
        s_part = SalesService.refund_sale(sale.id, refund_amount=part_amt, reason="Item return", user_id=manager_user.id)
        assert s_part.status == SaleStatus.PARTIALLY_REFUNDED
        assert s_part.refund_amount == part_amt
        assert s_part.net_amount == total - part_amt

        # Cannot void a partially refunded sale
        with pytest.raises(ValidationError):
            SalesService.void_sale(sale.id, reason="Try voiding refunded", user_id=manager_user.id)

        # Complete the remaining refund
        remaining = total - part_amt
        s_full = SalesService.refund_sale(sale.id, refund_amount=remaining, reason="Remaining refund", user_id=manager_user.id)
        assert s_full.status == SaleStatus.REFUNDED
        assert s_full.refund_amount == total
        assert s_full.net_amount == Decimal("0.00")

        # Further refund should be rejected
        with pytest.raises(ValidationError):
            SalesService.refund_sale(sale.id, refund_amount=Decimal("1.00"), user_id=manager_user.id)


def test_reprint_receipt_audit_log(app, cashier_user, sample_catalog):
    with app.app_context():
        prod = sample_catalog["product"]
        sale = POSService.checkout(
            user_id=cashier_user.id,
            items_data=[{"product_id": prod.id, "quantity": 1}],
            payment_method=PaymentMethod.CASH,
            cash_tendered=10.00
        )
        SalesService.record_receipt_reprint(sale.id, user_id=cashier_user.id, ip_address="127.0.0.1")
        log = AuditLog.query.filter_by(action="RECEIPT_REPRINTED").first()
        assert log is not None
        assert f"sale #{sale.id}" in log.details
