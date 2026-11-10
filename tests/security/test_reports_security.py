import pytest
from datetime import date
from decimal import Decimal
from app.extensions import db
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.catalog.models import Product, Category
from app.modules.sales.models import Sale, SaleItem, SaleStatus


def test_unauthenticated_reports_redirect(client):
    """Test unauthenticated users are redirected to login."""
    endpoints = [
        "/reports/",
        "/reports/profit-loss",
        "/reports/products",
        "/reports/inventory",
        "/reports/attendance",
        "/reports/registers",
        "/reports/export/pnl-csv",
        "/reports/export/products-csv",
        "/reports/export/sales-csv",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 302
        assert "/auth/login" in resp.location


def test_staff_and_barista_forbidden_on_financial_reports(client, staff_user, barista_user):
    """Test non-management staff and baristas cannot view P&L or export financial statements."""
    for user in [staff_user, barista_user]:
        client.post("/auth/login", data={"username": user.username, "password": f"{user.role.capitalize()}123!"}, follow_redirects=True)

        resp_pnl = client.get("/reports/profit-loss")
        assert resp_pnl.status_code == 403

        resp_inv = client.get("/reports/inventory")
        assert resp_inv.status_code == 403

        resp_att = client.get("/reports/attendance")
        assert resp_att.status_code == 403

        resp_pnl_csv = client.get("/reports/export/pnl-csv")
        assert resp_pnl_csv.status_code == 403

        client.get("/auth/logout")


def test_cashier_operational_access_and_financial_restriction(client, cashier_user):
    """Test cashier has access to operational reports (products, registers) but forbidden from full P&L."""
    client.post("/auth/login", data={"username": cashier_user.username, "password": "Cashier123!"}, follow_redirects=True)

    # Operational views allowed:
    resp_prod = client.get("/reports/products")
    assert resp_prod.status_code == 200

    resp_reg = client.get("/reports/registers")
    assert resp_reg.status_code == 200

    # Financial views restricted:
    resp_pnl = client.get("/reports/profit-loss")
    assert resp_pnl.status_code == 403

    resp_pnl_csv = client.get("/reports/export/pnl-csv")
    assert resp_pnl_csv.status_code == 403


def test_csv_formula_injection_defense(client, manager_user):
    """Test that CSV exports escape spreadsheet formula injection tokens (=, +, -, @)."""
    # Create product with malicious title
    cat = Category(name="=CMD()", slug="cmd-cat", is_active=True)
    db.session.add(cat)
    db.session.flush()

    prod = Product(
        name="+SUM(1,2)",
        slug="sum-exploit",
        sku="@DDE",
        category_id=cat.id,
        base_price=Decimal("10.00"),
        is_active=True,
    )
    db.session.add(prod)
    db.session.flush()

    sale = Sale(
        invoice_no="INV-SEC-001",
        user_id=manager_user.id,
        customer_name="-HYPERLINK('http://evil.com')",
        subtotal_amount=Decimal("10.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("10.00"),
        payment_method="Cash",
        status=SaleStatus.COMPLETED,
    )
    db.session.add(sale)
    db.session.flush()

    item = SaleItem(
        sale_id=sale.id,
        product_id=prod.id,
        product_name=prod.name,
        quantity=1,
        unit_price=Decimal("10.00"),
        unit_cost=Decimal("2.00"),
        subtotal=Decimal("10.00"),
    )
    db.session.add(item)
    db.session.commit()

    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    # Check products CSV
    resp_p = client.get("/reports/export/products-csv")
    assert resp_p.status_code == 200
    p_text = resp_p.data.decode("utf-8")
    assert "'+SUM(1,2)" in p_text
    assert "'@DDE" in p_text
    assert "'=CMD()" in p_text

    # Check sales CSV
    resp_s = client.get("/reports/export/sales-csv")
    assert resp_s.status_code == 200
    s_text = resp_s.data.decode("utf-8")
    assert "'-HYPERLINK('http://evil.com')" in s_text
