import pytest
from app.modules.catalog.models import Product, Category


def test_unauthenticated_catalog_redirect(client):
    res = client.get("/catalog/")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_cashier_barista_staff_can_view_catalog(client, cashier_user, barista_user, staff_user, sample_catalog):
    for user, pwd in [(cashier_user, "Cashier123!"), (barista_user, "Barista123!"), (staff_user, "Staff123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd})
        res = client.get("/catalog/")
        assert res.status_code == 200
        assert b"Menu Catalog" in res.data
        client.get("/auth/logout")


def test_cashier_cannot_create_or_modify_catalog(client, cashier_user, sample_catalog):
    client.post("/auth/login", data={"username": "test_cashier", "password": "Cashier123!"})
    prod = sample_catalog["product"]

    # Attempt to open create page
    res = client.get("/catalog/products/create")
    assert res.status_code == 403

    # Attempt to POST create product
    res = client.post("/catalog/products/create", data={
        "name": "Unauthorized Drink",
        "category_id": sample_catalog["category"].id,
        "base_price": "100.00"
    })
    assert res.status_code == 403

    # Attempt to POST toggle availability
    res = client.post(f"/catalog/products/{prod.id}/toggle")
    assert res.status_code == 403

    # Attempt to access category management
    res = client.get("/catalog/categories")
    assert res.status_code == 403


def test_manager_and_owner_can_manage_catalog(client, manager_user, owner_user, sample_catalog):
    cat = sample_catalog["category"]
    for user, pwd in [(manager_user, "Manager123!"), (owner_user, "Owner123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd})

        # Can open create product page
        res = client.get("/catalog/products/create")
        assert res.status_code == 200

        # Can access category management
        res = client.get("/catalog/categories")
        assert res.status_code == 200

        client.get("/auth/logout")
