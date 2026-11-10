"""Unit & Integration tests for Dashboard Visualizations & Chart APIs."""
import pytest
from app.modules.dashboard.routes import get_orders_chart_data, get_stock_chart_data


def test_get_orders_chart_data_today(app):
    """Test orders chart aggregation for 'today' period."""
    with app.app_context():
        data = get_orders_chart_data("today")
        assert data["success"] is True
        assert data["period"] == "today"
        assert len(data["labels"]) == 9  # 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00
        assert len(data["orders"]) == 9
        assert len(data["revenue"]) == 9
        assert isinstance(data["total_orders"], int)
        assert isinstance(data["total_revenue"], float)
        assert data["formatted_revenue"].startswith("₱")


def test_get_orders_chart_data_periods(app):
    """Test orders chart aggregation for week, month, and year periods."""
    with app.app_context():
        for period in ["week", "month", "year"]:
            data = get_orders_chart_data(period)
            assert data["success"] is True
            assert data["period"] == period
            assert len(data["labels"]) > 0
            assert len(data["orders"]) == len(data["labels"])
            assert len(data["revenue"]) == len(data["labels"])
            assert data["total_orders"] >= 0


def test_get_stock_chart_data(app):
    """Test stock chart data structure and calculations."""
    with app.app_context():
        data = get_stock_chart_data()
        assert data["success"] is True
        assert "labels" in data
        assert "current" in data
        assert "reorder" in data
        assert "units" in data
        assert "stock_pct" in data
        assert "statuses" in data
        assert isinstance(data["total_items"], int)
        assert isinstance(data["low_stock_count"], int)


def test_api_orders_chart_authenticated(client, owner_user):
    """API endpoint /api/orders-chart should return JSON for authenticated user."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner_user.id)

    res = client.get("/api/orders-chart?period=week")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["period"] == "week"


def test_api_stock_chart_authenticated(client, owner_user):
    """API endpoint /api/stock-chart should return JSON for authenticated user."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner_user.id)

    res = client.get("/api/stock-chart")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "labels" in json_data


def test_dashboard_index_renders_graphs(client, owner_user):
    """Dashboard page should render the Orders chart and Stock Levels canvas elements."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner_user.id)

    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "ordersChart" in html
    assert "stockChart" in html
    assert "data-period=\"today\"" in html
    assert "data-period=\"week\"" in html
    assert "data-period=\"month\"" in html
    assert "data-period=\"year\"" in html
    assert "initialChartData" in html
    assert "dashboard.js" in html
