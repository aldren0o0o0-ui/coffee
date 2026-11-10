import pytest
from app.modules.pos.services import POSService
from app.modules.sales.models import Sale, SaleStatus


def test_unauthenticated_sales_access_redirects(client):
    res = client.get("/sales/")
    assert res.status_code == 302
    assert "/auth/login" in res.location


def test_barista_cannot_access_sales_ledger(client, barista_user):
    client.post("/auth/login", data={"username": "test_barista", "password": "Barista123!"}, follow_redirects=True)
    res = client.get("/sales/")
    assert res.status_code == 403


def test_cashier_cannot_refund_or_void(client, cashier_user, sample_catalog):
    # Cashier creates sale
    prod = sample_catalog["product"]
    sale = POSService.checkout(
        user_id=cashier_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Cash",
        cash_tendered=10.00
    )

    # Cashier logs in
    client.post("/auth/login", data={"username": "test_cashier", "password": "Cashier123!"}, follow_redirects=True)

    # Cashier can view ledger
    res = client.get("/sales/")
    assert res.status_code == 200

    # Cashier cannot refund
    res_refund = client.post(f"/sales/{sale.id}/refund", data={"reason": "Cashier unauthorized refund"}, follow_redirects=True)
    assert res_refund.status_code == 403

    # Cashier cannot void
    res_void = client.post(f"/sales/{sale.id}/void", data={"reason": "Cashier unauthorized void"}, follow_redirects=True)
    assert res_void.status_code == 403


def test_invalid_refund_tampering_prevented(client, manager_user, sample_catalog):
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    prod = sample_catalog["product"]
    sale = POSService.checkout(
        user_id=manager_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Cash",
        cash_tendered=10.00
    )

    # Try to refund $9999.00 (tampered amount)
    res = client.post(
        f"/sales/{sale.id}/refund",
        data={"amount": "9999.00", "reason": "Tamper amount"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"cannot exceed remaining balance" in res.data
