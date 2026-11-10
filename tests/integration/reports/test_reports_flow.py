import pytest
from datetime import date
from decimal import Decimal
from app.extensions import db
from app.modules.sales.models import Sale, SaleStatus


def test_reports_views_flow(client, manager_user, sample_catalog):
    """Test accessing all reporting sub-views as manager."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    endpoints = [
        "/reports/",
        "/reports/profit-loss",
        "/reports/products",
        "/reports/inventory",
        "/reports/attendance",
        "/reports/registers",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200
        assert b"Executive Overview" in resp.data or b"P&amp;L Statement" in resp.data or b"P&L Statement" in resp.data or b"Product Sales" in resp.data


def test_reports_period_filtering(client, manager_user):
    """Test switching time periods and custom date parameters."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    today_str = date.today().strftime("%Y-%m-%d")

    # 1. Standard period filter
    resp = client.get("/reports/profit-loss?period=today")
    assert resp.status_code == 200
    assert b"Today (" in resp.data

    # 2. Custom date range filter
    resp_custom = client.get(f"/reports/profit-loss?period=custom&start_date={today_str}&end_date={today_str}")
    assert resp_custom.status_code == 200
    assert today_str.encode() in resp_custom.data


def test_reports_csv_exports(client, manager_user, sample_catalog):
    """Test all sanitized CSV report export downloads."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    # 1. P&L CSV export
    pnl_csv = client.get("/reports/export/pnl-csv?period=this_month")
    assert pnl_csv.status_code == 200
    assert pnl_csv.mimetype == "text/csv"
    assert b"Gross Sales Revenue" in pnl_csv.data
    assert b"Cost of Goods Sold" in pnl_csv.data
    assert b"Net Operating Income" in pnl_csv.data

    # 2. Products CSV export
    prod_csv = client.get("/reports/export/products-csv?period=this_month")
    assert prod_csv.status_code == 200
    assert prod_csv.mimetype == "text/csv"
    assert b"Product SKU,Product Name,Category" in prod_csv.data

    # 3. Sales CSV export
    sales_csv = client.get("/reports/export/sales-csv")
    assert sales_csv.status_code == 200
    assert sales_csv.mimetype == "text/csv"
    assert b"Invoice No,Date,Customer" in sales_csv.data


def test_reports_template_navigation_and_roles(client, manager_user, cashier_user):
    """Regression test verifying template navigation consistency and role checks across all 6 views."""
    # 1. Manager sees all sub-menu links across all views
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    endpoints = [
        "/reports/",
        "/reports/profit-loss",
        "/reports/products",
        "/reports/inventory",
        "/reports/attendance",
        "/reports/registers",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200
        # Check sub-menu links are present in all views
        assert b"Executive Overview" in resp.data
        assert b"P&amp;L Statement" in resp.data or b"P&L Statement" in resp.data
        assert b"Product Sales &amp; Margins" in resp.data or b"Product Sales & Margins" in resp.data
        assert b"Inventory &amp; Valuation" in resp.data or b"Inventory & Valuation" in resp.data
        assert b"Staff Labor &amp; Hours" in resp.data or b"Staff Labor & Hours" in resp.data
        assert b"POS Register Audits" in resp.data
        # Check handlePeriodChange JS function is present in all views
        assert b"handlePeriodChange" in resp.data

    # Check print stylesheet is present in profit_loss
    resp_pnl = client.get("/reports/profit-loss")
    assert b"@media print" in resp_pnl.data
    assert b"pnl-statement-card" in resp_pnl.data

    client.get("/auth/logout")

    # 2. Cashier only sees authorized links in sub-menu (no forbidden 403 links)
    client.post("/auth/login", data={"username": cashier_user.username, "password": "Cashier123!"}, follow_redirects=True)

    resp_prod = client.get("/reports/products")
    assert resp_prod.status_code == 200
    assert b"Product Sales &amp; Margins" in resp_prod.data or b"Product Sales & Margins" in resp_prod.data
    assert b"POS Register Audits" in resp_prod.data
    # Forbidden links should NOT be present for cashiers
    assert b"P&amp;L Statement" not in resp_prod.data and b"P&L Statement" not in resp_prod.data
    assert b"Inventory &amp; Valuation" not in resp_prod.data and b"Inventory & Valuation" not in resp_prod.data
    assert b"Staff Labor &amp; Hours" not in resp_prod.data and b"Staff Labor & Hours" not in resp_prod.data
    assert b"Export Products CSV" not in resp_prod.data

    resp_reg = client.get("/reports/registers")
    assert resp_reg.status_code == 200
    assert b"POS Register Audits" in resp_reg.data
    assert b"P&amp;L Statement" not in resp_reg.data and b"P&L Statement" not in resp_reg.data
    assert b"Inventory &amp; Valuation" not in resp_reg.data and b"Inventory & Valuation" not in resp_reg.data
    assert b"Staff Labor &amp; Hours" not in resp_reg.data and b"Staff Labor & Hours" not in resp_reg.data


def test_reports_template_parameter_preservation(client, manager_user):
    """Regression test verifying query parameters (period, start_date, end_date) are preserved in sub-menu links."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    start_date = "2026-01-01"
    end_date = "2026-01-15"
    query_str = f"period=custom&start_date={start_date}&end_date={end_date}"

    endpoints = [
        f"/reports/?{query_str}",
        f"/reports/profit-loss?{query_str}",
        f"/reports/products?{query_str}",
        f"/reports/inventory?{query_str}",
        f"/reports/attendance?{query_str}",
        f"/reports/registers?{query_str}",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200
        # Verify that start_date and end_date appear inside the sub-menu links or custom date inputs
        assert start_date.encode() in resp.data
        assert end_date.encode() in resp.data


def test_reports_index_edge_cases_and_error_resilience(client, manager_user, app):
    """Regression test verifying index.html renders safely with malformed query params and None/edge-case values."""
    from flask import render_template
    from decimal import Decimal

    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    # 1. Invalid custom dates should fallback gracefully without 500 Internal Server Error
    resp_bad = client.get("/reports/?period=custom&start_date=invalid-date&end_date=bad-date")
    assert resp_bad.status_code == 200
    assert b"Executive Financial" in resp_bad.data

    resp_empty = client.get("/reports/?period=custom&start_date=&end_date=")
    assert resp_empty.status_code == 200
    assert b"Executive Financial" in resp_empty.data

    # 2. Direct Jinja2 template render resilience tests with None/empty edge case data
    with app.test_request_context("/reports/"):
        # Case A: kpis with None numeric values (sales_growth_pct, net_operating_profit)
        kpis_none = {
            "sales_growth_pct": None,
            "net_operating_profit": None,
            "net_sales": None,
            "gross_sales": None,
            "refunds": None,
            "gross_profit": None,
            "gross_margin_pct": None,
            "cogs": None,
            "total_operating_costs": None,
            "operating_expenses": None,
            "labor_cost": None,
            "net_margin_pct": None,
            "order_count": 0,
            "aov": None,
            "period_label": "Edge Case Period",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        }
        payments_edge = {
            "total_amount": None,
            "methods": [
                {"method": None, "transactions": None, "amount": None, "share_pct": None}
            ]
        }
        categories_edge = {
            "total_revenue": None,
            "categories": [
                {"category_id": 1, "name": None, "units_sold": None, "revenue": None, "revenue_share": None}
            ]
        }

        # Should render without throwing TypeError or UndefinedError
        html_a = render_template(
            "reports/index.html",
            kpis=kpis_none,
            payments=payments_edge,
            categories=categories_edge,
            selected_period="custom",
            start_date="",
            end_date=""
        )
        assert len(html_a) > 0

        # Case B: completely empty dictionaries
        html_b = render_template(
            "reports/index.html",
            kpis={},
            payments={},
            categories={},
            selected_period="today",
            start_date="",
            end_date=""
        )
        assert len(html_b) > 0

        # Case C: None passed for all models/dictionaries
        html_c = render_template(
            "reports/index.html",
            kpis=None,
            payments=None,
            categories=None,
            selected_period="today",
            start_date="",
            end_date=""
        )
        assert len(html_c) > 0


