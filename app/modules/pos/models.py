from datetime import datetime
from app.extensions import db


class POSRegisterShift(db.Model):
    __tablename__ = "pos_register_shifts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    opening_cash = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    closing_cash = db.Column(db.Numeric(10, 2), nullable=True)
    expected_cash = db.Column(db.Numeric(10, 2), nullable=True)
    total_sales_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    total_orders_count = db.Column(db.Integer, nullable=False, default=0)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.String(255), nullable=True)

    # Relationships
    user = db.relationship("User", backref="pos_shifts")
    sales = db.relationship("Sale", backref="shift", lazy="dynamic")

    @property
    def discrepancy(self):
        if self.closing_cash is not None and self.expected_cash is not None:
            return round(float(self.closing_cash) - float(self.expected_cash), 2)
        return 0.00

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "cashier_name": self.user.full_name if self.user else "Unknown",
            "opening_cash": float(self.opening_cash),
            "closing_cash": float(self.closing_cash) if self.closing_cash is not None else None,
            "expected_cash": float(self.expected_cash) if self.expected_cash is not None else None,
            "discrepancy": self.discrepancy,
            "total_sales_amount": float(self.total_sales_amount),
            "total_orders_count": self.total_orders_count,
            "opened_at": self.opened_at.strftime("%Y-%m-%d %H:%M"),
            "closed_at": self.closed_at.strftime("%Y-%m-%d %H:%M") if self.closed_at else None,
            "is_active": self.is_active,
        }
