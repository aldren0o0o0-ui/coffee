from datetime import datetime
from decimal import Decimal
from app.extensions import db


class PaymentMethod:
    CASH = "Cash"
    CARD = "Card"
    QR = "QR"
    SPLIT = "Split"
    ALL = [CASH, CARD, QR, SPLIT]


class PaymentStatus:
    SUCCESS = "SUCCESS"
    REFUNDED = "REFUNDED"
    VOIDED = "VOIDED"
    ALL = [SUCCESS, REFUNDED, VOIDED]


class SaleStatus:
    COMPLETED = "completed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    VOIDED = "voided"
    ALL = [COMPLETED, REFUNDED, PARTIALLY_REFUNDED, VOIDED]


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    idempotency_key = db.Column(db.String(64), unique=True, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("pos_register_shifts.id", ondelete="SET NULL"), nullable=True, index=True)

    cashier = db.relationship("User", foreign_keys=[user_id], backref="sales")
    customer_name = db.Column(db.String(120), default="Guest", nullable=False)
    subtotal_amount = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(32), nullable=False, default=PaymentMethod.CASH, index=True)
    cash_tendered = db.Column(db.Numeric(10, 2), default=0.00)
    change_due = db.Column(db.Numeric(10, 2), default=0.00)
    status = db.Column(db.String(32), default=SaleStatus.COMPLETED, nullable=False, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Phase 7 Ledger & Audit additions
    payment_status = db.Column(db.String(32), default="PAID", nullable=False)
    refund_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    refund_reason = db.Column(db.String(255), nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    refunded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voided_at = db.Column(db.DateTime, nullable=True)
    voided_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason = db.Column(db.String(255), nullable=True)

    items = db.relationship("SaleItem", backref="sale", cascade="all, delete-orphan", lazy="joined")
    payments = db.relationship("Payment", backref="sale", cascade="all, delete-orphan", lazy="joined", order_by="Payment.created_at.asc()")
    refunded_by = db.relationship("User", foreign_keys=[refunded_by_id])
    voided_by = db.relationship("User", foreign_keys=[voided_by_id])

    @property
    def total_cost(self):
        return sum(Decimal(str(item.unit_cost)) * Decimal(str(item.quantity)) for item in self.items)

    @property
    def gross_profit(self):
        return Decimal(str(self.subtotal_amount)) - self.total_cost

    @property
    def net_amount(self):
        refunded = Decimal(str(self.refund_amount or "0.00"))
        if self.status == SaleStatus.VOIDED:
            return Decimal("0.00")
        return max(Decimal(str(self.total_amount)) - refunded, Decimal("0.00"))

    @property
    def is_refundable(self):
        if self.status == SaleStatus.VOIDED:
            return False
        total = Decimal(str(self.total_amount))
        refunded = Decimal(str(self.refund_amount or "0.00"))
        return total > refunded

    @property
    def is_voidable(self):
        return self.status == SaleStatus.COMPLETED and Decimal(str(self.refund_amount or "0.00")) == Decimal("0.00")

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_no": self.invoice_no,
            "idempotency_key": self.idempotency_key,
            "cashier_name": self.cashier.full_name if self.cashier else "Staff",
            "customer_name": self.customer_name,
            "subtotal_amount": float(self.subtotal_amount),
            "tax_amount": float(self.tax_amount),
            "discount_amount": float(self.discount_amount),
            "total_amount": float(self.total_amount),
            "net_amount": float(self.net_amount),
            "refund_amount": float(self.refund_amount or 0.0),
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "cash_tendered": float(self.cash_tendered) if self.cash_tendered else 0.0,
            "change_due": float(self.change_due) if self.change_due else 0.0,
            "status": self.status,
            "is_refundable": self.is_refundable,
            "is_voidable": self.is_voidable,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "items": [item.to_dict() for item in self.items],
            "payments": [p.to_dict() for p in self.payments]
        }


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    product_name = db.Column(db.String(120), nullable=False)
    variant_name = db.Column(db.String(120), nullable=True)
    options_data = db.Column(db.JSON, nullable=True)
    options_price = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    variant = db.relationship("ProductVariant", foreign_keys=[variant_id])

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "product_name": self.product_name,
            "variant_name": self.variant_name,
            "options_data": self.options_data,
            "options_price": float(self.options_price) if self.options_price else 0.0,
            "unit_price": float(self.unit_price),
            "unit_cost": float(self.unit_cost),
            "quantity": self.quantity,
            "subtotal": float(self.subtotal)
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_method = db.Column(db.String(32), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reference_no = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), default=PaymentStatus.SUCCESS, nullable=False, index=True)
    cash_tendered = db.Column(db.Numeric(10, 2), nullable=True)
    change_due = db.Column(db.Numeric(10, 2), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "payment_method": self.payment_method,
            "amount": float(self.amount),
            "reference_no": self.reference_no,
            "status": self.status,
            "cash_tendered": float(self.cash_tendered) if self.cash_tendered is not None else None,
            "change_due": float(self.change_due) if self.change_due is not None else None,
            "created_by": self.created_by.full_name if self.created_by else "System",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
