import pytest
from datetime import date
from app.modules.expenses.services import ExpenseService


def test_expense_creation_and_sum(app, owner_user):
    with app.app_context():
        cat = ExpenseService.create_category("Utilities", "Electricity and water")
        assert cat.id is not None

        exp1 = ExpenseService.create_expense("Power Bill", cat.id, 120.00, user_id=owner_user.id)
        exp2 = ExpenseService.create_expense("Water Bill", cat.id, 45.00, user_id=owner_user.id)

        total = ExpenseService.get_total_expenses()
        assert total == 165.00
