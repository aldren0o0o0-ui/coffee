from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from sqlalchemy import func, case
from app.extensions import db
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus, ExpensePaymentMethod
from app.modules.expenses.validators import (
    validate_expense_payload,
    validate_category_payload,
    validate_expense_can_be_edited,
    validate_expense_can_be_voided,
)
from app.modules.auth.models import AuditLog
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_query
from app.core.utilities import generate_expense_number


class ExpenseService:
    @staticmethod
    def get_categories(active_only=False):
        query = ExpenseCategory.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(ExpenseCategory.name.asc()).all()

    @staticmethod
    def get_category_by_id(category_id):
        cat = db.session.get(ExpenseCategory, category_id)
        if not cat:
            raise NotFoundError(f"Expense category #{category_id} not found.")
        return cat

    @staticmethod
    def create_category(name, description="", code=None, user_id=None):
        clean_name = name.strip()
        if not code or not code.strip():
            # Auto-generate a clean alphanumeric uppercase code
            base_code = re.sub(r"[^A-Za-z0-9]", "", clean_name).upper()[:6] or "CAT"
            # Ensure unique code
            existing = ExpenseCategory.query.filter_by(code=base_code).first()
            if existing:
                code = f"{base_code}_{int(datetime.utcnow().timestamp()) % 10000}"
            else:
                code = base_code
        else:
            code = code.strip().upper()

        validate_category_payload(clean_name, code=code)

        cat = ExpenseCategory(
            name=clean_name,
            code=code,
            description=description.strip() if description else "",
            is_active=True
        )
        db.session.add(cat)
        db.session.commit()

        AuditLog.log(
            action="EXPENSE_CATEGORY_CREATED",
            details=f"Created expense category '{cat.name}' [{cat.code}]",
            user_id=user_id
        )
        return cat

    @staticmethod
    def update_category(category_id, name, description="", code=None, is_active=True, user_id=None):
        cat = ExpenseService.get_category_by_id(category_id)
        clean_name = name.strip()
        clean_code = code.strip().upper() if code else cat.code

        validate_category_payload(clean_name, code=clean_code, exclude_id=cat.id)

        cat.name = clean_name
        cat.code = clean_code
        cat.description = description.strip() if description else ""
        cat.is_active = bool(is_active)
        db.session.commit()

        AuditLog.log(
            action="EXPENSE_CATEGORY_UPDATED",
            details=f"Updated expense category #{cat.id} '{cat.name}' [{cat.code}]",
            user_id=user_id
        )
        return cat

    @staticmethod
    def get_expenses_paginated(
        page=1, per_page=15, category_id=None, status=None,
        payment_method=None, date_from=None, date_to=None, search=None
    ):
        query = Expense.query
        if category_id:
            query = query.filter_by(category_id=category_id)
        if status:
            query = query.filter_by(status=status)
        if payment_method:
            query = query.filter_by(payment_method=payment_method)
        if date_from:
            query = query.filter(Expense.expense_date >= date_from)
        if date_to:
            query = query.filter(Expense.expense_date <= date_to)
        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                (Expense.title.ilike(s)) |
                (Expense.expense_number.ilike(s)) |
                (Expense.vendor_payee.ilike(s))
            )

        query = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_expense_by_id(expense_id):
        exp = db.session.get(Expense, expense_id)
        if not exp:
            raise NotFoundError("Expense record not found.")
        return exp

    @staticmethod
    def get_expense_by_number(expense_number):
        exp = Expense.query.filter_by(expense_number=expense_number.strip()).first()
        if not exp:
            raise NotFoundError(f"Expense #{expense_number} not found.")
        return exp

    @staticmethod
    def create_expense(
        title, category_id, amount, expense_date=None, notes="",
        user_id=None, vendor_payee=None, payment_method="Cash"
    ):
        validate_expense_payload(
            title=title,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            expense_date=expense_date
        )

        dec_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        exp_number = generate_expense_number(prefix="EXP")

        exp = Expense(
            expense_number=exp_number,
            title=title.strip(),
            category_id=int(category_id),
            amount=dec_amount,
            expense_date=expense_date or date.today(),
            payment_method=payment_method or ExpensePaymentMethod.CASH,
            vendor_payee=vendor_payee.strip() if vendor_payee else None,
            status=ExpenseStatus.RECORDED,
            notes=notes.strip() if notes else None,
            recorded_by_id=user_id
        )
        db.session.add(exp)
        db.session.commit()

        AuditLog.log(
            action="EXPENSE_CREATED",
            details=f"Recorded expense #{exp.expense_number}: '{exp.title}' (${exp.amount:.2f})",
            user_id=user_id
        )
        return exp

    @staticmethod
    def update_expense(
        expense_id, title, category_id, amount, expense_date=None,
        notes="", user_id=None, vendor_payee=None, payment_method="Cash"
    ):
        exp = ExpenseService.get_expense_by_id(expense_id)
        validate_expense_can_be_edited(exp)
        validate_expense_payload(
            title=title,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            expense_date=expense_date
        )

        dec_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        exp.title = title.strip()
        exp.category_id = int(category_id)
        exp.amount = dec_amount
        if expense_date:
            exp.expense_date = expense_date
        exp.payment_method = payment_method or ExpensePaymentMethod.CASH
        exp.vendor_payee = vendor_payee.strip() if vendor_payee else None
        exp.notes = notes.strip() if notes else None
        db.session.commit()

        AuditLog.log(
            action="EXPENSE_UPDATED",
            details=f"Updated expense #{exp.expense_number}: '{exp.title}' (${exp.amount:.2f})",
            user_id=user_id
        )
        return exp

    @staticmethod
    def void_expense(expense_id, reason="", user_id=None):
        """
        Void an expense record.
        NEVER physically deletes financial history; marks as VOIDED with audit trail.
        """
        exp = ExpenseService.get_expense_by_id(expense_id)
        validate_expense_can_be_voided(exp)

        exp.status = ExpenseStatus.VOIDED
        exp.voided_at = datetime.utcnow()
        exp.voided_by_id = user_id
        exp.void_reason = reason.strip() if reason else "Voided by manager"
        db.session.commit()

        AuditLog.log(
            action="EXPENSE_VOIDED",
            details=f"Voided expense #{exp.expense_number} (${exp.amount:.2f}). Reason: {exp.void_reason}",
            user_id=user_id
        )
        return exp

    @staticmethod
    def delete_expense(expense_id, user_id=None):
        """
        Backward compatibility wrapper:
        Delegates to void_expense rather than physically destroying financial records.
        """
        return ExpenseService.void_expense(expense_id, reason="Voided via delete action", user_id=user_id)

    @staticmethod
    def get_total_expenses(start_date=None, end_date=None, category_id=None):
        """
        Backward compatibility helper returning float sum of active expenses.
        Excludes VOIDED records.
        """
        query = db.session.query(func.coalesce(func.sum(Expense.amount), 0.00)).filter(
            Expense.status != ExpenseStatus.VOIDED
        )
        if start_date:
            query = query.filter(Expense.expense_date >= start_date)
        if end_date:
            query = query.filter(Expense.expense_date <= end_date)
        if category_id:
            query = query.filter_by(category_id=category_id)
        return float(query.scalar())

    @staticmethod
    def get_expense_summary(date_from=None, date_to=None, category_id=None):
        """Deterministic SQL aggregations for operating expense summary KPIs."""
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        query = db.session.query(
            func.coalesce(func.sum(case(((Expense.status != ExpenseStatus.VOIDED) & (Expense.expense_date == today), Expense.amount), else_=0)), 0).label("today_total"),
            func.coalesce(func.sum(case(((Expense.status != ExpenseStatus.VOIDED) & (Expense.expense_date >= start_of_week), Expense.amount), else_=0)), 0).label("week_total"),
            func.coalesce(func.sum(case(((Expense.status != ExpenseStatus.VOIDED) & (Expense.expense_date >= start_of_month), Expense.amount), else_=0)), 0).label("month_total"),
            func.coalesce(func.sum(case((Expense.status != ExpenseStatus.VOIDED, Expense.amount), else_=0)), 0).label("period_total"),
            func.count(case((Expense.status != ExpenseStatus.VOIDED, Expense.id))).label("active_count"),
            func.count(case((Expense.status == ExpenseStatus.VOIDED, Expense.id))).label("voided_count")
        )

        if date_from:
            query = query.filter(Expense.expense_date >= date_from)
        if date_to:
            query = query.filter(Expense.expense_date <= date_to)
        if category_id:
            query = query.filter(Expense.category_id == category_id)

        res = query.one()
        return {
            "today_total": Decimal(str(res.today_total)),
            "week_total": Decimal(str(res.week_total)),
            "month_total": Decimal(str(res.month_total)),
            "period_total": Decimal(str(res.period_total)),
            "active_count": int(res.active_count or 0),
            "voided_count": int(res.voided_count or 0)
        }

    @staticmethod
    def get_category_breakdown(date_from=None, date_to=None):
        """SQL GROUP BY aggregation for expense breakdown by category."""
        query = db.session.query(
            ExpenseCategory.id,
            ExpenseCategory.name,
            ExpenseCategory.code,
            func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
            func.count(Expense.id).label("count")
        ).join(Expense, Expense.category_id == ExpenseCategory.id).filter(
            Expense.status != ExpenseStatus.VOIDED
        )

        if date_from:
            query = query.filter(Expense.expense_date >= date_from)
        if date_to:
            query = query.filter(Expense.expense_date <= date_to)

        query = query.group_by(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.code).order_by(
            func.sum(Expense.amount).desc()
        )
        results = query.all()

        total_sum = sum(Decimal(str(r.total_amount)) for r in results) or Decimal("1.00")
        breakdown = []
        for r in results:
            cat_sum = Decimal(str(r.total_amount))
            pct = round((float(cat_sum) / float(total_sum)) * 100, 1)
            breakdown.append({
                "id": r.id,
                "name": r.name,
                "code": r.code,
                "total_amount": cat_sum,
                "count": r.count,
                "percentage": pct
            })
        return breakdown
