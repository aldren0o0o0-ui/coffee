from decimal import Decimal
from app.extensions import db
from app.modules.pos.services import POSService
from app.modules.sales.models import Sale, SaleStatus, PaymentStatus
from app.modules.inventory.models import Ingredient


def test_pos_to_sales_ledger_and_refund_flow(client, manager_user, sample_catalog):
    # Authenticate as manager
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    prod = sample_catalog["product"]
    sale = POSService.checkout(
        user_id=manager_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Cash",
        cash_tendered=20.00
    )

    # 1. View sales ledger index
    res = client.get("/sales/")
    assert res.status_code == 200
    assert sale.invoice_no.encode() in res.data
    assert b"Completed" in res.data

    # 2. View sale transaction detail
    res_detail = client.get(f"/sales/{sale.id}")
    assert res_detail.status_code == 200
    assert sale.invoice_no.encode() in res_detail.data
    assert b"Payment Records" in res_detail.data
    assert b"SUCCESS" in res_detail.data

    # 3. Process partial refund via POST route
    refund_res = client.post(
        f"/sales/{sale.id}/refund",
        data={"amount": "2.00", "reason": "Customer dissatisfied with sweetness"},
        follow_redirects=True
    )
    assert refund_res.status_code == 200
    assert b"refund processed successfully" in refund_res.data

    # Verify updated state in DB
    refreshed_sale = db.session.get(Sale, sale.id)
    assert refreshed_sale.status == SaleStatus.PARTIALLY_REFUNDED
    assert refreshed_sale.refund_amount == Decimal("2.00")
    assert len(refreshed_sale.payments) == 2  # Original + Refund entry
    assert refreshed_sale.payments[1].status == PaymentStatus.REFUNDED
    assert refreshed_sale.payments[1].amount == Decimal("-2.00")


def test_refund_preserves_inventory_deduction(client, manager_user, sample_catalog):
    """
    CRITICAL COFFEE SME BUSINESS RULE:
    Prepared drink refunds must NOT automatically restore perishable ingredients (coffee beans, milk).
    Discarded beverages are operational waste, not inventory restock.
    """
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    prod = sample_catalog["product"]
    bean = sample_catalog["ingredients"][0]

    initial_stock = Decimal(str(bean.current_quantity))

    # Checkout drink with recipe
    sale = POSService.checkout(
        user_id=manager_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Card"
    )

    post_checkout_bean = db.session.get(Ingredient, bean.id)
    stock_after_sale = Decimal(str(post_checkout_bean.current_quantity))
    assert stock_after_sale < initial_stock  # Ingredients were consumed

    # Process refund
    client.post(
        f"/sales/{sale.id}/refund",
        data={"amount": str(sale.total_amount), "reason": "Spilled drink return"},
        follow_redirects=True
    )

    refreshed_bean = db.session.get(Ingredient, bean.id)
    # Stock must remain unchanged after refund (no phantom inventory restock)
    assert Decimal(str(refreshed_bean.current_quantity)) == stock_after_sale


def test_void_flow_via_manager_action(client, manager_user, sample_catalog):
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    prod = sample_catalog["product"]
    sale = POSService.checkout(
        user_id=manager_user.id,
        items_data=[{"product_id": prod.id, "quantity": 1}],
        payment_method="Cash",
        cash_tendered=10.00
    )

    # Void transaction via POST
    void_res = client.post(
        f"/sales/{sale.id}/void",
        data={"reason": "Cashier entered incorrect table items"},
        follow_redirects=True
    )
    assert void_res.status_code == 200
    assert b"has been voided" in void_res.data

    refreshed = db.session.get(Sale, sale.id)
    assert refreshed.status == SaleStatus.VOIDED
    assert refreshed.is_voidable is False
    assert refreshed.is_refundable is False
