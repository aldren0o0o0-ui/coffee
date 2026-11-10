from app.modules.pos.services import POSService


def test_sales_and_receipt_flow(client, owner_user, sample_catalog):
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    prod = sample_catalog["product"]
    sale = POSService.checkout(
        user_id=owner_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Cash",
        cash_tendered=10.00
    )

    # View sales index
    res = client.get("/sales/")
    assert res.status_code == 200
    assert sale.invoice_no.encode() in res.data

    # View receipt
    res = client.get(f"/sales/{sale.id}/receipt")
    assert res.status_code == 200
    assert b"Receipt #" in res.data
