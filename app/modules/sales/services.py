from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import func, case
from app.extensions import db
from app.modules.sales.models import Sale, SaleItem, Payment, SaleStatus, PaymentStatus, PaymentMethod
from app.modules.sales.validators import validate_sale_can_be_refunded, validate_sale_can_be_voided
from app.modules.pos.models import POSRegisterShift
from app.modules.auth.models import AuditLog
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_query


class SalesService:
    @staticmethod
    def get_sales_paginated(
        page=1, per_page=15, date_from=None, date_to=None,
        search=None, status=None, payment_method=None, cashier_id=None, shift_id=None
    ):
        query = Sale.query
        if date_from:
            dt_from = datetime.combine(date_from, time.min)
            query = query.filter(Sale.created_at >= dt_from)
        if date_to:
            dt_to = datetime.combine(date_to, time.max)
            query = query.filter(Sale.created_at <= dt_to)
        if status:
            query = query.filter_by(status=status)
        if payment_method:
            query = query.filter_by(payment_method=payment_method)
        if cashier_id:
            query = query.filter_by(user_id=cashier_id)
        if shift_id:
            query = query.filter_by(shift_id=shift_id)
        if search:
            s = f"%{search.strip()}%"
            query = query.filter((Sale.invoice_no.ilike(s)) | (Sale.customer_name.ilike(s)))

        query = query.order_by(Sale.created_at.desc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_sales_summary(date_from=None, date_to=None, cashier_id=None, shift_id=None):
        """Authoritative deterministic SQL aggregation for sales summary metrics."""
        query = db.session.query(
            func.coalesce(func.sum(case((Sale.status != SaleStatus.VOIDED, Sale.total_amount), else_=0)), 0).label("gross_sales"),
            func.coalesce(func.sum(Sale.refund_amount), 0).label("refund_amount"),
            func.coalesce(func.sum(case((Sale.status != SaleStatus.VOIDED, Sale.discount_amount), else_=0)), 0).label("total_discounts"),
            func.coalesce(func.sum(case((Sale.status != SaleStatus.VOIDED, Sale.tax_amount), else_=0)), 0).label("total_tax"),
            func.count(case((Sale.status != SaleStatus.VOIDED, Sale.id))).label("transaction_count"),
            func.count(case((Sale.status == SaleStatus.COMPLETED, Sale.id))).label("completed_count"),
            func.count(case((Sale.status == SaleStatus.VOIDED, Sale.id))).label("voided_count"),
            func.count(case((Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]), Sale.id))).label("refunded_count"),
            func.coalesce(func.sum(case(((Sale.status != SaleStatus.VOIDED) & (Sale.payment_method == PaymentMethod.CASH), Sale.total_amount), else_=0)), 0).label("cash_sales"),
            func.coalesce(func.sum(case(((Sale.status != SaleStatus.VOIDED) & (Sale.payment_method != PaymentMethod.CASH), Sale.total_amount), else_=0)), 0).label("non_cash_sales"),
        )

        if date_from:
            dt_from = datetime.combine(date_from, time.min)
            query = query.filter(Sale.created_at >= dt_from)
        if date_to:
            dt_to = datetime.combine(date_to, time.max)
            query = query.filter(Sale.created_at <= dt_to)
        if cashier_id:
            query = query.filter(Sale.user_id == cashier_id)
        if shift_id:
            query = query.filter(Sale.shift_id == shift_id)

        res = query.one()

        gross_sales = Decimal(str(res.gross_sales))
        refund_amount = Decimal(str(res.refund_amount))
        net_sales = max(gross_sales - refund_amount, Decimal("0.00"))
        tx_count = int(res.transaction_count or 0)
        avg_value = (net_sales / tx_count) if tx_count > 0 else Decimal("0.00")

        return {
            "gross_sales": gross_sales,
            "refund_amount": refund_amount,
            "net_sales": net_sales,
            "total_discounts": Decimal(str(res.total_discounts)),
            "total_tax": Decimal(str(res.total_tax)),
            "transaction_count": tx_count,
            "completed_count": int(res.completed_count or 0),
            "voided_count": int(res.voided_count or 0),
            "refunded_count": int(res.refunded_count or 0),
            "cash_sales": Decimal(str(res.cash_sales)),
            "non_cash_sales": Decimal(str(res.non_cash_sales)),
            "avg_transaction_value": avg_value.quantize(Decimal("0.01"))
        }

    @staticmethod
    def get_sale_by_id(sale_id):
        sale = db.session.get(Sale, sale_id)
        if not sale:
            raise NotFoundError("Order/Sale record not found.")
        return sale

    @staticmethod
    def get_sale_by_invoice(invoice_no):
        sale = Sale.query.filter_by(invoice_no=invoice_no.strip()).first()
        if not sale:
            raise NotFoundError("Invoice not found.")
        return sale

    @staticmethod
    def void_sale(sale_id, reason="", user_id=None):
        """
        Void a sale transaction before settlement or during same shift.
        Cancels financial record, updates associated payments, adjusts active shift totals if applicable.
        Raw materials for prepared beverages are not returned (coffee waste rule).
        """
        sale = SalesService.get_sale_by_id(sale_id)
        validate_sale_can_be_voided(sale)

        sale.status = SaleStatus.VOIDED
        sale.payment_status = PaymentStatus.VOIDED
        sale.voided_at = datetime.utcnow()
        sale.voided_by_id = user_id
        sale.void_reason = reason.strip() if reason else "Voided by manager"

        # Update payment records to VOIDED
        for p in sale.payments:
            p.status = PaymentStatus.VOIDED

        # If linked to an active shift, deduct from shift running sales total
        if sale.shift_id:
            shift = db.session.get(POSRegisterShift, sale.shift_id)
            if shift and shift.is_active:
                shift.total_sales_amount = max(
                    Decimal(str(shift.total_sales_amount or "0.00")) - Decimal(str(sale.total_amount)),
                    Decimal("0.00")
                )
                if shift.total_orders_count and shift.total_orders_count > 0:
                    shift.total_orders_count -= 1

        AuditLog.log(
            action="SALE_VOIDED",
            details=f"Voided sale #{sale.invoice_no}. Reason: {sale.void_reason}",
            user_id=user_id
        )

        db.session.commit()
        return sale

    @staticmethod
    def refund_sale(sale_id, refund_amount=None, reason="", user_id=None):
        """
        Process a full or partial refund on a completed sale.
        Creates an immutable refund Payment record, updates refund total and sale status.
        Raw ingredients are not returned to inventory for prepared drinks (coffee shop waste rule).
        """
        sale = SalesService.get_sale_by_id(sale_id)

        current_refunded = Decimal(str(sale.refund_amount or "0.00"))
        remaining_balance = Decimal(str(sale.total_amount)) - current_refunded

        if refund_amount is None:
            amt_to_refund = remaining_balance
        else:
            amt_to_refund = Decimal(str(refund_amount)).quantize(Decimal("0.01"))

        validate_sale_can_be_refunded(sale, refund_amount=amt_to_refund)

        new_total_refunded = (current_refunded + amt_to_refund).quantize(Decimal("0.01"))
        sale.refund_amount = new_total_refunded

        if new_total_refunded >= Decimal(str(sale.total_amount)):
            sale.status = SaleStatus.REFUNDED
            sale.payment_status = PaymentStatus.REFUNDED
        else:
            sale.status = SaleStatus.PARTIALLY_REFUNDED
            sale.payment_status = "PARTIAL_REFUND"

        sale.refunded_at = datetime.utcnow()
        sale.refunded_by_id = user_id
        sale.refund_reason = reason.strip() if reason else "Refund processed"

        note_entry = f"Refunded ${amt_to_refund:.2f} by user #{user_id}: {reason}" if reason else f"Refunded ${amt_to_refund:.2f} by user #{user_id}"
        sale.notes = f"{sale.notes} | {note_entry}" if sale.notes else note_entry

        # Create immutable refund Payment entry (negative amount)
        refund_payment = Payment(
            sale_id=sale.id,
            payment_method=sale.payment_method,
            amount=-amt_to_refund,
            reference_no=f"REF-{sale.invoice_no}",
            status=PaymentStatus.REFUNDED,
            created_by_id=user_id,
            created_at=datetime.utcnow()
        )
        db.session.add(refund_payment)

        AuditLog.log(
            action="SALE_REFUNDED",
            details=f"Refunded ${amt_to_refund:.2f} for sale #{sale.invoice_no}. Reason: {sale.refund_reason}",
            user_id=user_id
        )

        db.session.commit()
        return sale

    @staticmethod
    def record_receipt_reprint(sale_id, user_id=None, ip_address=None):
        AuditLog.log(
            action="RECEIPT_REPRINTED",
            details=f"Receipt reprinted for sale #{sale_id} by user #{user_id}",
            user_id=user_id,
            ip_address=ip_address
        )
