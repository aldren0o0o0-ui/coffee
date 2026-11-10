import pytest
from app.modules.inventory.models import Ingredient


def test_unauthenticated_inventory_redirect(client):
    res = client.get("/inventory/")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_inventory_view_permissions_matrix(client, cashier_user, barista_user, staff_user, sample_inventory):
    # Cashier & Barista can view inventory overview and movements
    for user, pwd in [(cashier_user, "Cashier123!"), (barista_user, "Barista123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd})
        assert client.get("/inventory/").status_code == 200
        assert client.get("/inventory/items").status_code == 200
        assert client.get("/inventory/movements").status_code == 200
        client.get("/auth/logout")

    # Staff can view inventory overview and items, but CANNOT view movements
    client.post("/auth/login", data={"username": "test_staff", "password": "Staff123!"})
    assert client.get("/inventory/").status_code == 200
    assert client.get("/inventory/items").status_code == 200
    assert client.get("/inventory/movements").status_code == 403
    client.get("/auth/logout")


def test_cashier_barista_staff_cannot_modify_stock(client, cashier_user, barista_user, staff_user, sample_inventory):
    item = sample_inventory["item"]
    for user, pwd in [(cashier_user, "Cashier123!"), (barista_user, "Barista123!"), (staff_user, "Staff123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd})

        # Cannot open create item page
        assert client.get("/inventory/items/create").status_code == 403

        # Cannot POST stock adjustment
        res = client.post("/inventory/adjust", data={
            "ingredient_id": item.id,
            "quantity": "5.0",
            "reason": "Unauthorized attempt"
        })
        assert res.status_code == 403

        # Cannot access purchases
        assert client.get("/inventory/purchases").status_code == 403

        client.get("/auth/logout")


def test_manager_and_owner_can_adjust_stock_and_manage_inventory(client, manager_user, owner_user, sample_inventory):
    item = sample_inventory["item"]
    for user, pwd in [(manager_user, "Manager123!"), (owner_user, "Owner123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd})

        # Can open create item page
        assert client.get("/inventory/items/create").status_code == 200

        # Can open purchases
        assert client.get("/inventory/purchases").status_code == 200

        # Can adjust stock
        res = client.post("/inventory/adjust", data={
            "ingredient_id": item.id,
            "quantity": "2.0",
            "reason": "Authorized manager/owner adjustment"
        }, follow_redirects=True)
        assert res.status_code == 200

        client.get("/auth/logout")
