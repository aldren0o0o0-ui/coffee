import pytest
from app.modules.expenses.services import ExpenseService
from app.modules.expenses.models import Expense, ExpenseStatus


def test_unauthenticated_expenses_access_redirects(client):
    res = client.get("/expenses/")
    assert res.status_code == 302
    assert "/auth/login" in res.location


def test_cashier_barista_staff_cannot_access_expenses(client, cashier_user, barista_user, staff_user):
    # Cashier
    client.post("/auth/login", data={"username": "test_cashier", "password": "Cashier123!"}, follow_redirects=True)
    assert client.get("/expenses/").status_code == 403
    assert client.get("/expenses/create").status_code == 403
    assert client.get("/expenses/categories").status_code == 403
    client.post("/auth/logout")

    # Barista
    client.post("/auth/login", data={"username": "test_barista", "password": "Barista123!"}, follow_redirects=True)
    assert client.get("/expenses/").status_code == 403
    assert client.get("/expenses/create").status_code == 403
    client.post("/auth/logout")

    # Staff
    client.post("/auth/login", data={"username": "test_staff", "password": "Staff123!"}, follow_redirects=True)
    assert client.get("/expenses/").status_code == 403
    assert client.get("/expenses/create").status_code == 403
    client.post("/auth/logout")


def test_manager_and_owner_can_access_expenses(client, manager_user, owner_user):
    # Manager
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)
    assert client.get("/expenses/").status_code == 200
    assert client.get("/expenses/create").status_code == 200
    assert client.get("/expenses/categories").status_code == 200
    client.post("/auth/logout")

    # Owner
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)
    assert client.get("/expenses/").status_code == 200
    assert client.get("/expenses/create").status_code == 200
    assert client.get("/expenses/categories").status_code == 200


def test_negative_expense_amount_tamper_rejected(client, manager_user):
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)
    cat = ExpenseService.create_category("Test Security Cat", code="TSECCAT", user_id=manager_user.id)

    res = client.post(
        "/expenses/create",
        data={
            "title": "Tampered Negative Expense",
            "category_id": str(cat.id),
            "amount": "-50.00"
        },
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"must be strictly greater than zero" in res.data
