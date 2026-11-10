import pytest
from decimal import Decimal
from datetime import date, timedelta
from app.extensions import db
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus, ExpensePaymentMethod
from app.modules.expenses.services import ExpenseService
from app.core.exceptions import ValidationError, NotFoundError
from app.modules.auth.models import AuditLog


def test_category_creation_and_uniqueness(app, owner_user):
    with app.app_context():
        cat1 = ExpenseService.create_category("Store Lease", code="RENT", description="Monthly building lease", user_id=owner_user.id)
        assert cat1.id is not None
        assert cat1.code == "RENT"
        assert cat1.is_active is True

        # Duplicate name should fail
        with pytest.raises(ValidationError):
            ExpenseService.create_category("Store Lease", code="RENT2", user_id=owner_user.id)

        # Duplicate code should fail
        with pytest.raises(ValidationError):
            ExpenseService.create_category("Warehouse Lease", code="RENT", user_id=owner_user.id)


def test_category_active_toggle_and_inactive_guard(app, owner_user):
    with app.app_context():
        cat = ExpenseService.create_category("Temporary Marketing", code="MKTG", user_id=owner_user.id)
        assert cat.is_active is True

        # Deactivate
        ExpenseService.update_category(cat.id, cat.name, code=cat.code, is_active=False, user_id=owner_user.id)
        assert cat.is_active is False

        # Creating expense under inactive category must fail
        with pytest.raises(ValidationError):
            ExpenseService.create_expense(
                title="Flyer Printing",
                category_id=cat.id,
                amount=50.00,
                user_id=owner_user.id
            )


def test_expense_creation_number_generation_and_validation(app, owner_user):
    with app.app_context():
        cat = ExpenseService.create_category("Store Utilities", code="UTIL", user_id=owner_user.id)

        # Negative amount rejected
        with pytest.raises(ValidationError):
            ExpenseService.create_expense("Power Bill", cat.id, -10.00, user_id=owner_user.id)

        # Zero amount rejected
        with pytest.raises(ValidationError):
            ExpenseService.create_expense("Power Bill", cat.id, 0.00, user_id=owner_user.id)

        # Missing title rejected
        with pytest.raises(ValidationError):
            ExpenseService.create_expense("   ", cat.id, 50.00, user_id=owner_user.id)

        # Invalid payment method rejected
        with pytest.raises(ValidationError):
            ExpenseService.create_expense("Power Bill", cat.id, 50.00, payment_method="Bitcoin", user_id=owner_user.id)

        # Valid expense creation
        exp = ExpenseService.create_expense(
            title="Electric Utility",
            category_id=cat.id,
            amount=145.50,
            payment_method=ExpensePaymentMethod.BANK,
            vendor_payee="City Power",
            user_id=owner_user.id
        )
        assert exp.id is not None
        assert exp.expense_number.startswith("EXP-")
        assert exp.amount == Decimal("145.50")
        assert exp.status == ExpenseStatus.RECORDED
        assert exp.vendor_payee == "City Power"
        assert exp.is_editable is True
        assert exp.is_voidable is True


def test_expense_update_and_voiding_lifecycle(app, manager_user):
    with app.app_context():
        cat = ExpenseService.create_category("Equipment Repairs", code="REPAIR", user_id=manager_user.id)
        exp = ExpenseService.create_expense(
            title="Grinder Burr Replacement",
            category_id=cat.id,
            amount=80.00,
            user_id=manager_user.id
        )

        # Update
        updated = ExpenseService.update_expense(
            expense_id=exp.id,
            title="Grinder Burr Replacement & Calibration",
            category_id=cat.id,
            amount=95.00,
            vendor_payee="Tech Services Co.",
            user_id=manager_user.id
        )
        assert updated.title == "Grinder Burr Replacement & Calibration"
        assert updated.amount == Decimal("95.00")
        assert updated.vendor_payee == "Tech Services Co."

        # Void expense (non-destructive)
        voided = ExpenseService.void_expense(exp.id, reason="Paid from personal funds", user_id=manager_user.id)
        assert voided.status == ExpenseStatus.VOIDED
        assert voided.void_reason == "Paid from personal funds"
        assert voided.voided_at is not None
        assert voided.voided_by_id == manager_user.id

        # Record remains historically in database
        check_db = db.session.get(Expense, exp.id)
        assert check_db is not None
        assert check_db.status == ExpenseStatus.VOIDED

        # Cannot edit voided expense
        with pytest.raises(ValidationError):
            ExpenseService.update_expense(exp.id, title="Try edit", category_id=cat.id, amount=100.00, user_id=manager_user.id)

        # Cannot void already voided expense
        with pytest.raises(ValidationError):
            ExpenseService.void_expense(exp.id, reason="Try void again", user_id=manager_user.id)


def test_expense_summary_and_category_breakdown(app, owner_user):
    with app.app_context():
        cat1 = ExpenseService.create_category("Facility Rent", code="RENT_FAC", user_id=owner_user.id)
        cat2 = ExpenseService.create_category("Internet & Telecom", code="TELCO", user_id=owner_user.id)

        exp1 = ExpenseService.create_expense("Monthly Lease", cat1.id, 1000.00, user_id=owner_user.id)
        exp2 = ExpenseService.create_expense("Fiber Internet", cat2.id, 100.00, user_id=owner_user.id)
        exp_void = ExpenseService.create_expense("Wrong Invoice", cat2.id, 50.00, user_id=owner_user.id)
        ExpenseService.void_expense(exp_void.id, reason="Mistake", user_id=owner_user.id)

        # Summary must exclude voided
        summary = ExpenseService.get_expense_summary()
        assert summary["period_total"] == Decimal("1100.00")
        assert summary["active_count"] == 2
        assert summary["voided_count"] == 1

        # Category breakdown
        breakdown = ExpenseService.get_category_breakdown()
        assert len(breakdown) == 2
        # Rent should be ~90.9%, Telco ~9.1%
        rent_entry = next(b for b in breakdown if b["code"] == "RENT_FAC")
        assert rent_entry["total_amount"] == Decimal("1000.00")
        assert rent_entry["percentage"] > 90.0
