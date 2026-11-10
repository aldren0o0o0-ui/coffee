from datetime import datetime, date
from decimal import Decimal
from app.extensions import db


class ExpensePaymentMethod:
    CASH = "Cash"
    BANK = "Bank Transfer"
    CARD = "Card"
    E_WALLET = "E-Wallet"
    OTHER = "Other"
    ALL = [CASH, BANK, CARD, E_WALLET, OTHER]


class ExpenseStatus:
    RECORDED = "RECORDED"
    VOIDED = "VOIDED"
    ALL = [RECORDED, VOIDED]


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    expenses = db.relationship("Expense", backref="category", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    payment_method = db.Column(db.String(32), default=ExpensePaymentMethod.CASH, nullable=False)
    vendor_payee = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(32), default=ExpenseStatus.RECORDED, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voided_at = db.Column(db.DateTime, nullable=True)
    voided_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id], backref="recorded_expenses")
    voided_by = db.relationship("User", foreign_keys=[voided_by_id])

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        db.Index("ix_expenses_date_cat_status", "expense_date", "category_id", "status"),
    )

    @property
    def is_recorded(self):
        return self.status == ExpenseStatus.RECORDED

    @property
    def is_voided(self):
        return self.status == ExpenseStatus.VOIDED

    @property
    def is_editable(self):
        return self.status == ExpenseStatus.RECORDED

    @property
    def is_voidable(self):
        return self.status == ExpenseStatus.RECORDED

    def to_dict(self):
        return {
            "id": self.id,
            "expense_number": self.expense_number,
            "title": self.title,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "category_code": self.category.code if self.category else "",
            "amount": float(self.amount),
            "expense_date": self.expense_date.strftime("%Y-%m-%d"),
            "payment_method": self.payment_method,
            "vendor_payee": self.vendor_payee or "",
            "status": self.status,
            "notes": self.notes or "",
            "recorded_by": self.recorded_by.full_name if self.recorded_by else "System",
            "voided_at": self.voided_at.strftime("%Y-%m-%d %H:%M:%S") if self.voided_at else None,
            "voided_by": self.voided_by.full_name if self.voided_by else None,
            "void_reason": self.void_reason or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
