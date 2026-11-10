import os
import calendar
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, current_app, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import text, func
from app.extensions import db
from app.modules.users.models import User
from app.modules.auth.models import AuditLog

dashboard_bp = Blueprint("dashboard", __name__)


def get_orders_chart_data(period="today"):
    """Aggregate orders count and sales revenue for today, week, month, or year."""
    from app.modules.sales.models import Sale, SaleStatus

    period = (period or "today").lower().strip()
    if period not in ("today", "week", "month", "year"):
        period = "today"

    now = datetime.utcnow()
    today = now.date()

    labels = []
    orders_counts = []
    revenues = []

    try:
        if period == "today":
            # 2-hour increments from 06:00 to 22:00
            labels = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
            orders_counts = [0] * len(labels)
            revenues = [0.0] * len(labels)

            start_dt = datetime.combine(today, time.min)
            end_dt = datetime.combine(today, time.max)

            sales = Sale.query.filter(
                Sale.status == SaleStatus.COMPLETED,
                Sale.created_at >= start_dt,
                Sale.created_at <= end_dt
            ).all()

            for s in sales:
                h = s.created_at.hour
                if h <= 6:
                    idx = 0
                elif h >= 22:
                    idx = len(labels) - 1
                else:
                    idx = min(len(labels) - 1, (h - 6 + 1) // 2)
                orders_counts[idx] += 1
                revenues[idx] += float(s.total_amount or 0)

        elif period == "week":
            # Last 7 calendar days ending today
            days = [today - timedelta(days=i) for i in reversed(range(7))]
            labels = [d.strftime("%a %d") for d in days]
            orders_counts = [0] * len(days)
            revenues = [0.0] * len(days)
            date_map = {d: idx for idx, d in enumerate(days)}

            start_dt = datetime.combine(days[0], time.min)
            sales = Sale.query.filter(
                Sale.status == SaleStatus.COMPLETED,
                Sale.created_at >= start_dt
            ).all()

            for s in sales:
                s_date = s.created_at.date()
                if s_date in date_map:
                    idx = date_map[s_date]
                    orders_counts[idx] += 1
                    revenues[idx] += float(s.total_amount or 0)

        elif period == "month":
            # 6 five-day blocks across current calendar month
            year, month = today.year, today.month
            num_days = calendar.monthrange(year, month)[1]
            bucket_defs = [
                (1, 5, "1-5"),
                (6, 10, "6-10"),
                (11, 15, "11-15"),
                (16, 20, "16-20"),
                (21, 25, "21-25"),
                (26, num_days, f"26-{num_days}"),
            ]
            month_name = calendar.month_abbr[month]
            labels = [f"{b[2]} {month_name}" for b in bucket_defs]
            orders_counts = [0] * len(bucket_defs)
            revenues = [0.0] * len(bucket_defs)

            start_dt = datetime(year, month, 1, 0, 0, 0)
            end_dt = datetime(year, month, num_days, 23, 59, 59)

            sales = Sale.query.filter(
                Sale.status == SaleStatus.COMPLETED,
                Sale.created_at >= start_dt,
                Sale.created_at <= end_dt
            ).all()

            for s in sales:
                day = s.created_at.day
                for idx, (b_start, b_end, _) in enumerate(bucket_defs):
                    if b_start <= day <= b_end:
                        orders_counts[idx] += 1
                        revenues[idx] += float(s.total_amount or 0)
                        break

        elif period == "year":
            # 12 calendar months for current year
            year = today.year
            labels = [calendar.month_abbr[m] for m in range(1, 13)]
            orders_counts = [0] * 12
            revenues = [0.0] * 12

            start_dt = datetime(year, 1, 1, 0, 0, 0)
            end_dt = datetime(year, 12, 31, 23, 59, 59)

            sales = Sale.query.filter(
                Sale.status == SaleStatus.COMPLETED,
                Sale.created_at >= start_dt,
                Sale.created_at <= end_dt
            ).all()

            for s in sales:
                m = s.created_at.month
                if 1 <= m <= 12:
                    orders_counts[m - 1] += 1
                    revenues[m - 1] += float(s.total_amount or 0)

    except Exception:
        pass

    revenues = [round(r, 2) for r in revenues]
    total_orders = sum(orders_counts)
    total_revenue = round(sum(revenues), 2)
    avg_ticket = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

    return {
        "success": True,
        "period": period,
        "labels": labels,
        "orders": orders_counts,
        "revenue": revenues,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "formatted_revenue": f"₱{total_revenue:,.2f}",
        "avg_ticket": avg_ticket,
        "formatted_avg_ticket": f"₱{avg_ticket:,.2f}"
    }


def get_stock_chart_data():
    """Retrieve active inventory ingredients ranked by reorder urgency."""
    from app.modules.inventory.models import Ingredient
    items_data = []
    low_stock_count = 0
    critical_stock_count = 0
    healthy_stock_count = 0
    total_items = 0

    try:
        items = Ingredient.query.filter_by(is_active=True).all()
        total_items = len(items)

        for item in items:
            curr = float(item.current_quantity or 0)
            reorder = float(item.reorder_level or 0)
            unit = ""
            if hasattr(item, "unit_of_measure") and item.unit_of_measure:
                unit = item.unit_of_measure.code
            elif hasattr(item, "unit") and item.unit:
                unit = item.unit

            # Calculate buffer ratio relative to reorder point
            if reorder > 0:
                ratio = curr / reorder
            else:
                ratio = 2.0 if curr > 0 else 0.0

            # Percentage buffer (100% = at reorder threshold)
            pct_val = round(ratio * 100, 1)

            if curr <= 0.5 * reorder if reorder > 0 else curr == 0:
                status = "critical"
                critical_stock_count += 1
                low_stock_count += 1
            elif curr <= reorder:
                status = "low"
                low_stock_count += 1
            else:
                status = "healthy"
                healthy_stock_count += 1

            items_data.append({
                "name": item.name,
                "sku": item.sku or "",
                "current": round(curr, 1),
                "reorder": round(reorder, 1),
                "unit": unit,
                "ratio": ratio,
                "stock_pct": pct_val,
                "status": status
            })

        # Sort by urgency: lowest stock buffer first
        items_data.sort(key=lambda x: (x["ratio"], x["current"]))

    except Exception:
        pass

    # Cap display to top 8 items to preserve dashboard visual balance
    display_items = items_data[:8]

    return {
        "success": True,
        "labels": [i["name"] for i in display_items],
        "current": [i["current"] for i in display_items],
        "reorder": [i["reorder"] for i in display_items],
        "units": [i["unit"] for i in display_items],
        "stock_pct": [i["stock_pct"] for i in display_items],
        "statuses": [i["status"] for i in display_items],
        "total_items": total_items,
        "low_stock_count": low_stock_count,
        "critical_stock_count": critical_stock_count,
        "healthy_stock_count": healthy_stock_count
    }


@dashboard_bp.route("/api/orders-chart", methods=["GET"])
@login_required
def api_orders_chart():
    period = request.args.get("period", "today")
    data = get_orders_chart_data(period)
    return jsonify(data)


@dashboard_bp.route("/api/stock-chart", methods=["GET"])
@login_required
def api_stock_chart():
    data = get_stock_chart_data()
    return jsonify(data)


@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    # Verify live DB status
    db_connected = False
    try:
        db.session.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 1. Staff and User Stats
    total_users = 0
    active_users = 0
    if current_user.has_permission("users.view"):
        try:
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
        except Exception:
            pass

    recent_logs = []
    if current_user.is_owner:
        try:
            recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()
        except Exception:
            pass

    # 2. Sales & POS Operations (Today's Pulse)
    today_start = datetime.combine(date.today(), time.min)
    today_sales_total = Decimal("0.00")
    today_orders_count = 0
    avg_ticket = Decimal("0.00")
    recent_sales = []

    try:
        from app.modules.sales.models import Sale, SaleStatus
        sales_today_query = Sale.query.filter(
            Sale.status == SaleStatus.COMPLETED,
            Sale.created_at >= today_start
        )
        total_val = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0.00)).filter(
            Sale.status == SaleStatus.COMPLETED,
            Sale.created_at >= today_start
        ).scalar()
        if total_val is not None:
            today_sales_total = Decimal(str(total_val))

        today_orders_count = sales_today_query.count()
        if today_orders_count > 0:
            avg_ticket = today_sales_total / Decimal(str(today_orders_count))

        # Recent transactions feed
        if current_user.has_permission("sales.view"):
            recent_sales = Sale.query.order_by(Sale.id.desc()).limit(5).all()
    except Exception:
        pass

    # 3. Active Register Shift
    active_shift = None
    try:
        from app.modules.pos.models import POSRegisterShift
        active_shift = POSRegisterShift.query.filter_by(is_active=True).first()
    except Exception:
        pass

    # 4. Inventory Health & Low Stock Watchlist
    low_stock_items = []
    low_stock_count = 0
    total_inventory_items = 0
    try:
        from app.modules.inventory.models import Ingredient
        total_inventory_items = Ingredient.query.filter_by(is_active=True).count()
        low_stock_query = Ingredient.query.filter(
            Ingredient.is_active == True,
            Ingredient.current_quantity <= Ingredient.reorder_level
        )
        low_stock_count = low_stock_query.count()
        low_stock_items = low_stock_query.limit(4).all()
    except Exception:
        pass

    # 5. Live Staff on Shift
    active_clocked_in_staff = 0
    try:
        from app.modules.employees.models import ShiftAttendance
        active_clocked_in_staff = ShiftAttendance.query.filter(ShiftAttendance.clock_out == None).count()
    except Exception:
        pass

    # Active Menu Products
    total_products = 0
    try:
        from app.modules.catalog.models import Product
        total_products = Product.query.filter_by(is_active=True).count()
    except Exception:
        pass

    # Initial chart data for zero-latency dashboard rendering
    orders_chart = get_orders_chart_data("today")
    stock_chart = get_stock_chart_data()

    system_info = {
        "db_connected": db_connected,
        "environment": os.environ.get("FLASK_ENV", "development"),
        "total_users": total_users,
        "active_users": active_users,
        "recent_logs": recent_logs,
        "today_sales_total": today_sales_total,
        "today_orders_count": today_orders_count,
        "avg_ticket": avg_ticket,
        "recent_sales": recent_sales,
        "active_shift": active_shift,
        "low_stock_count": low_stock_count,
        "low_stock_items": low_stock_items,
        "total_inventory_items": total_inventory_items,
        "active_clocked_in_staff": active_clocked_in_staff,
        "total_products": total_products,
        "orders_chart": orders_chart,
        "stock_chart": stock_chart,
    }

    return render_template("dashboard/index.html", system_info=system_info)
