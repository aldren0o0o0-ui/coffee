import re
from decimal import Decimal
from app.extensions import db
from app.core.exceptions import ValidationError
from app.modules.expenses.models import ExpenseCategory, Expense, ExpenseStatus, ExpensePaymentMethod


def validate_expense_payload(title, amount, category_id, payment_method=None, expense_date=None):
    if not title or not title.strip():
        raise ValidationError("Expense title is required.")
    if len(title.strip()) > 120:
        raise ValidationError("Expense title cannot exceed 120 characters.")

    if not category_id:
        raise ValidationError("Expense category is required.")
    try:
        cat_id = int(category_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid category reference.")

    cat = db.session.get(ExpenseCategory, cat_id)
    if not cat:
        raise ValidationError("Specified expense category does not exist.")
    if not cat.is_active:
        raise ValidationError(f"Category '{cat.name}' is inactive and cannot accept new expenses.")

    try:
        amt = Decimal(str(amount))
    except (ValueError, TypeError):
        raise ValidationError("Invalid expense amount format.")

    if amt <= Decimal("0.00"):
        raise ValidationError("Expense amount must be strictly greater than zero.")

    if payment_method and payment_method not in ExpensePaymentMethod.ALL:
        raise ValidationError(f"Invalid payment method '{payment_method}'. Allowed: {', '.join(ExpensePaymentMethod.ALL)}.")

    return True


def validate_category_payload(name, code=None, exclude_id=None):
    if not name or not name.strip():
        raise ValidationError("Category name is required.")
    clean_name = name.strip()
    if len(clean_name) < 2 or len(clean_name) > 64:
        raise ValidationError("Category name must be between 2 and 64 characters.")

    # Check duplicate name
    dup_query = ExpenseCategory.query.filter(ExpenseCategory.name.ilike(clean_name))
    if exclude_id:
        dup_query = dup_query.filter(ExpenseCategory.id != exclude_id)
    if dup_query.first():
        raise ValidationError(f"An expense category named '{clean_name}' already exists.")

    if code:
        clean_code = code.strip().upper()
        if not re.match(r"^[A-Z0-9_-]{2,32}$", clean_code):
            raise ValidationError("Category code must be 2-32 alphanumeric characters or hyphens/underscores.")
        dup_code = ExpenseCategory.query.filter_by(code=clean_code)
        if exclude_id:
            dup_code = dup_code.filter(ExpenseCategory.id != exclude_id)
        if dup_code.first():
            raise ValidationError(f"An expense category with code '{clean_code}' already exists.")

    return True


def validate_expense_can_be_edited(expense: Expense):
    if expense.status == ExpenseStatus.VOIDED:
        raise ValidationError("Voided expenses are immutable and cannot be edited.")
    return True


def validate_expense_can_be_voided(expense: Expense):
    if expense.status == ExpenseStatus.VOIDED:
        raise ValidationError("This expense is already voided.")
    return True
