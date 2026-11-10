from flask import Blueprint, request, render_template, Response, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import csv
import io
from app.core.decorators import roles_required
from app.core.permissions import Roles, Permissions
from app.modules.reports.services import ReportService
from app.modules.sales.models import Sale, SaleStatus
from app.modules.catalog.models import Category
from app.core.utilities import format_datetime, format_currency

reports_bp = Blueprint("reports", __name__)


def sanitize_csv_field(val):
    """Sanitize CSV cell against formula injection."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


@reports_bp.route("/", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER)
def index():
    """Executive Reports Dashboard."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    # Non-managers (cashiers) only have operational view permission
    if not current_user.is_manager_or_above:
        return redirect(url_for("reports.products"))

    kpis = ReportService.get_executive_kpis(period=period, start_date=start_date, end_date=end_date)
    payments = ReportService.get_payment_methods(period=period, start_date=start_date, end_date=end_date)
    categories = ReportService.get_category_performance(period=period, start_date=start_date, end_date=end_date)

    return render_template(
        "reports/index.html",
        kpis=kpis,
        payments=payments,
        categories=categories,
        selected_period=period,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/profit-loss", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def profit_loss():
    """Comprehensive Store Profit & Loss (P&L) Statement."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    pnl = ReportService.get_profit_and_loss(period=period, start_date=start_date, end_date=end_date)

    return render_template(
        "reports/profit_loss.html",
        pnl=pnl,
        selected_period=period,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/products", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER)
def products():
    """Product Sales & Gross Margin Performance Analytics."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    category_id = request.args.get("category_id", type=int)

    prod_data = ReportService.get_product_performance(
        period=period,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
    )
    cat_data = ReportService.get_category_performance(period=period, start_date=start_date, end_date=end_date)
    all_categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        "reports/products.html",
        prod_data=prod_data,
        cat_data=cat_data,
        categories=all_categories,
        selected_period=period,
        selected_category_id=category_id,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/inventory", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def inventory():
    """Raw Material Inventory Valuation & COGS Report."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    inv_data = ReportService.get_inventory_valuation_and_cogs(period=period, start_date=start_date, end_date=end_date)

    return render_template(
        "reports/inventory.html",
        inv_data=inv_data,
        selected_period=period,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/attendance", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def attendance():
    """Staff Labor Cost & Attendance Performance Report."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    labor_data = ReportService.get_staff_labor_report(period=period, start_date=start_date, end_date=end_date)

    return render_template(
        "reports/attendance.html",
        labor_data=labor_data,
        selected_period=period,
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/registers", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER)
def registers():
    """POS Register Cash Drawer & Shift Audits."""
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    audit_data = ReportService.get_pos_register_audits(period=period, start_date=start_date, end_date=end_date)

    return render_template(
        "reports/registers.html",
        audit_data=audit_data,
        selected_period=period,
        start_date=start_date,
        end_date=end_date,
    )


# -----------------------------------------------------------------
# CSV Data Exports (Formula Injection Protected)
# -----------------------------------------------------------------

@reports_bp.route("/export/pnl-csv", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def export_pnl_csv():
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    pnl = ReportService.get_profit_and_loss(period=period, start_date=start_date, end_date=end_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Line Item", "Amount ($)", "Percentage (%)"])

    writer.writerow(["Gross Sales Revenue", float(pnl["gross_sales"]), ""])
    writer.writerow(["Less: Customer Refunds & Returns", float(pnl["refunds"]), ""])
    writer.writerow(["Less: Discounts Given", float(pnl["discounts"]), ""])
    writer.writerow(["Net Sales Revenue", float(pnl["net_revenue"]), "100.0%"])
    writer.writerow(["", "", ""])

    writer.writerow(["Cost of Goods Sold (COGS)", float(pnl["cogs"]), f"{round(float(pnl['cogs'] / pnl['net_revenue'] * 100), 1) if pnl['net_revenue'] > 0 else 0.0}%"])
    writer.writerow(["Gross Operating Profit", float(pnl["gross_profit"]), f"{pnl['gross_margin_pct']}%"])
    writer.writerow(["", "", ""])

    writer.writerow(["Operating Overhead Expenses:", "", ""])
    for cat in pnl["expense_categories"]:
        writer.writerow([f"  {sanitize_csv_field(cat['category_name'])}", float(cat["amount"]), ""])
    writer.writerow(["  Staff Shift Labor Expenses", float(pnl["labor_cost"]), ""])
    writer.writerow(["Total Operating Overhead", float(pnl["total_operating_expenses"]), ""])
    writer.writerow(["", "", ""])

    writer.writerow(["Net Operating Income (EBITDA)", float(pnl["net_operating_income"]), f"{pnl['net_margin_pct']}%"])
    writer.writerow(["", "", ""])
    writer.writerow(["Disclosure", sanitize_csv_field(pnl["disclosure"]), ""])

    output.seek(0)
    filename = f"coffee_pnl_report_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/export/products-csv", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def export_products_csv():
    period = request.args.get("period", "this_month")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    category_id = request.args.get("category_id", type=int)

    prod_data = ReportService.get_product_performance(
        period=period,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Product SKU",
        "Product Name",
        "Category",
        "Units Sold",
        "Total Revenue ($)",
        "COGS ($)",
        "Gross Margin ($)",
        "Margin (%)",
        "Revenue Share (%)",
        "Avg Selling Price ($)",
    ])

    for it in prod_data["items"]:
        writer.writerow([
            sanitize_csv_field(it["sku"]),
            sanitize_csv_field(it["name"]),
            sanitize_csv_field(it["category_name"]),
            it["units_sold"],
            float(it["revenue"]),
            float(it["cogs"]),
            float(it["gross_margin"]),
            it["margin_pct"],
            it["revenue_share"],
            float(it["avg_price"]),
        ])

    output.seek(0)
    filename = f"product_sales_analytics_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/export/sales-csv", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def export_sales_csv():
    period = request.args.get("period", "")
    start_str = request.args.get("start_date", "")
    end_str = request.args.get("end_date", "")

    query = Sale.query.filter(Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]))
    if period or start_str or end_str:
        start_dt, end_dt, _ = ReportService.get_period_bounds(period or "custom", start_str or None, end_str or None)
        query = query.filter(Sale.created_at >= start_dt, Sale.created_at <= end_dt)

    sales = query.order_by(Sale.created_at.desc()).limit(1000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Invoice No", "Date", "Customer", "Subtotal", "Tax", "Discount", "Total", "Refunded", "Net", "Payment Method", "Status"])

    for s in sales:
        writer.writerow([
            sanitize_csv_field(s.invoice_no),
            s.created_at.strftime("%Y-%m-%d %H:%M"),
            sanitize_csv_field(s.customer_name),
            float(s.subtotal_amount),
            float(s.tax_amount),
            float(s.discount_amount),
            float(s.total_amount),
            float(s.refund_amount or 0.0),
            float(s.net_amount),
            sanitize_csv_field(s.payment_method),
            sanitize_csv_field(s.status),
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=coffee_sales_export.csv"},
    )
