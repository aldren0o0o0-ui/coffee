import pytest
from decimal import Decimal
from app.modules.pos.services import POSService
from app.modules.sales.models import Sale, SaleStatus, PaymentMethod
from app.extensions import db


def test_unauthenticated_pos_redirect(client):
    """Unauthenticated users must be redirected to login screen."""
    res = client.get("/pos/")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_pos_role_access_matrix(client, cashier_user, barista_user, manager_user, staff_user):
    """
    Role Matrix Verification:
    - Cashier, Barista, Manager can access POS.
    - Staff role has no POS permission and must receive 403 Forbidden.
    """
    # 1. Cashier -> 200 OK
    client.post("/auth/login", data={"username": cashier_user.username, "password": "Cashier123!"})
    res_cashier = client.get("/pos/")
    assert res_cashier.status_code == 200
    client.get("/auth/logout")

    # 2. Barista -> 200 OK
    client.post("/auth/login", data={"username": barista_user.username, "password": "Barista123!"})
    res_barista = client.get("/pos/")
    assert res_barista.status_code == 200
    client.get("/auth/logout")

    # 3. Manager -> 200 OK
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"})
    res_mgr = client.get("/pos/")
    assert res_mgr.status_code == 200
    client.get("/auth/logout")

    # 4. Staff -> 403 Forbidden
    client.post("/auth/login", data={"username": staff_user.username, "password": "Staff123!"})
    res_staff = client.get("/pos/")
    assert res_staff.status_code == 403
    client.get("/auth/logout")


def test_pos_tampering_immunity(client, cashier_user, sample_catalog):
    """
    Security check: Server-Authoritative Pricing Immunity.
    If a malicious or manipulated client submits $0.01 for a $5.00 product,
    the server must ignore client values and charge the authoritative DB price.
    """
    client.post("/auth/login", data={"username": cashier_user.username, "password": "Cashier123!"})

    prod = sample_catalog["product"]

    # Tampered JSON payload
    tampered_payload = {
        "items": [{
            "product_id": prod.id,
            "quantity": 1,
            "unit_price": 0.01,
            "subtotal": 0.01,
            "total": 0.01
        }],
        "payment_method": "Card",
        "customer_name": "Tamper Test",
        "cash_tendered": 0.01
    }

    res = client.post("/pos/checkout", json=tampered_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"

    # Sale total must reflect actual DB base price ($5.00) + 8% tax ($0.40) = $5.40, NOT $0.01!
    sale_data = data["data"]
    assert Decimal(str(sale_data["subtotal_amount"])) == Decimal("5.00")
    assert Decimal(str(sale_data["total_amount"])) == Decimal("5.40")
