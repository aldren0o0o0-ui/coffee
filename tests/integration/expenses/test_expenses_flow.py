from decimal import Decimal
from app.extensions import db
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.expenses.services import ExpenseService


def test_expenses_full_crud_and_void_flow(client, manager_user):
    # 1. Login as manager
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    # 2. Create Category via web route
    cat_res = client.post(
        "/expenses/categories",
        data={"name": "Facility Maintenance", "code": "MAINT", "description": "HVAC and plumbing"},
        follow_redirects=True
    )
    assert cat_res.status_code == 200
    assert b"created successfully" in cat_res.data

    cat = ExpenseCategory.query.filter_by(code="MAINT").first()
    assert cat is not None

    # 3. Create Expense via web form
    exp_res = client.post(
        "/expenses/create",
        data={
            "title": "Espresso Machine Pressure Valve Replacement",
            "category_id": str(cat.id),
            "amount": "175.50",
            "payment_method": "Bank Transfer",
            "vendor_payee": "Barista Repair Pros",
            "notes": "Invoice #BR-2026-99"
        },
        follow_redirects=True
    )
    assert exp_res.status_code == 200
    assert b"logged successfully" in exp_res.data

    exp = Expense.query.filter_by(category_id=cat.id).first()
    assert exp is not None
    assert exp.amount == Decimal("175.50")
    assert exp.status == ExpenseStatus.RECORDED

    # 4. View Ledger
    ledger_res = client.get("/expenses/")
    assert ledger_res.status_code == 200
    assert exp.expense_number.encode() in ledger_res.data
    assert b"Barista Repair Pros" in ledger_res.data

    # 5. View Detail
    detail_res = client.get(f"/expenses/{exp.id}")
    assert detail_res.status_code == 200
    assert exp.title.encode() in detail_res.data
    assert b"Invoice #BR-2026-99" in detail_res.data

    # 6. Edit Expense
    edit_res = client.post(
        f"/expenses/{exp.id}/edit",
        data={
            "title": "Espresso Machine Overhaul & Pressure Valve",
            "category_id": str(cat.id),
            "amount": "210.00",
            "payment_method": "Bank Transfer",
            "vendor_payee": "Barista Repair Pros",
            "notes": "Invoice #BR-2026-99 updated with labor"
        },
        follow_redirects=True
    )
    assert edit_res.status_code == 200
    assert b"updated successfully" in edit_res.data

    refreshed_exp = db.session.get(Expense, exp.id)
    assert refreshed_exp.amount == Decimal("210.00")
    assert refreshed_exp.title == "Espresso Machine Overhaul & Pressure Valve"

    # 7. Void Expense
    void_res = client.post(
        f"/expenses/{exp.id}/void",
        data={"reason": "Warranty covered by supplier"},
        follow_redirects=True
    )
    assert void_res.status_code == 200
    assert b"has been voided" in void_res.data

    voided_exp = db.session.get(Expense, exp.id)
    assert voided_exp.status == ExpenseStatus.VOIDED
    assert voided_exp.void_reason == "Warranty covered by supplier"
    assert voided_exp.voided_by_id == manager_user.id
