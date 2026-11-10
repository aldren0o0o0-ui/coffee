from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import func, or_
from app.extensions import db
from app.modules.sales.models import Sale, SaleItem, SaleStatus
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.inventory.models import Ingredient, Purchase, PurchaseStatus
from app.modules.catalog.models import Product, Category
from app.modules.pos.models import POSRegisterShift
from app.modules.employees.models import ShiftAttendance, EmployeeProfile, AttendanceStatus
from app.core.utilities import get_date_range_bounds, calculate_percentage_change


ZERO = Decimal("0.00")
TWO_PLACES = Decimal("0.01")


def to_dec(val) -> Decimal:
    """Safely convert any numeric value or None to Decimal."""
    if val is None:
        return ZERO
    return Decimal(str(val))


class ReportService:
    @staticmethod
    def get_period_bounds(period="this_month", start_date=None, end_date=None):
        """Standardized helper for period boundaries."""
        return get_date_range_bounds(period, start_date, end_date)

    # -------------------------------------------------------------
    # 1. Executive Dashboard KPIs
    # -------------------------------------------------------------

    @staticmethod
    def get_executive_kpis(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        # Calculate previous period for comparison
        duration = end_dt - start_dt
        prev_end_dt = start_dt - timedelta(seconds=1)
        prev_start_dt = prev_end_dt - duration

        # Query Current Period Sales
        sales_q = db.session.query(
            func.coalesce(func.sum(Sale.subtotal_amount), 0),
            func.coalesce(func.sum(Sale.tax_amount), 0),
            func.coalesce(func.sum(Sale.discount_amount), 0),
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.coalesce(func.sum(Sale.refund_amount), 0),
            func.count(Sale.id)
        ).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).first()

        gross_sales = to_dec(sales_q[3]).quantize(TWO_PLACES)
        refunds = to_dec(sales_q[4]).quantize(TWO_PLACES)
        net_sales = max(gross_sales - refunds, ZERO).quantize(TWO_PLACES)
        order_count = int(sales_q[5] or 0)
        aov = (net_sales / Decimal(order_count)).quantize(TWO_PLACES) if order_count > 0 else ZERO

        # Current COGS from SaleItems
        cogs_q = db.session.query(
            func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0)
        ).join(Sale, Sale.id == SaleItem.sale_id).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).scalar()
        cogs = to_dec(cogs_q).quantize(TWO_PLACES)

        gross_profit = max(net_sales - cogs, ZERO).quantize(TWO_PLACES)
        gross_margin_pct = round(float((gross_profit / net_sales) * 100), 1) if net_sales > ZERO else 0.0

        # Current Operating Expenses (posted non-voided)
        exp_q = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.status == ExpenseStatus.RECORDED,
            Expense.expense_date >= start_dt.date(),
            Expense.expense_date <= end_dt.date()
        ).scalar()
        operating_expenses = to_dec(exp_q).quantize(TWO_PLACES)

        # Labor Expenses from ShiftAttendances
        attendances = ShiftAttendance.query.filter(
            ShiftAttendance.clock_in >= start_dt,
            ShiftAttendance.clock_in <= end_dt
        ).all()
        labor_cost = ZERO
        total_worked_hours = 0.0
        for att in attendances:
            rate = to_dec(att.employee_profile.hourly_rate if att.employee_profile else Decimal("15.00"))
            hours = Decimal(str(round(att.total_hours, 2)))
            labor_cost += (rate * hours)
            total_worked_hours += att.total_hours
        labor_cost = labor_cost.quantize(TWO_PLACES)

        total_operating_costs = (operating_expenses + labor_cost).quantize(TWO_PLACES)
        net_operating_profit = (gross_profit - total_operating_costs).quantize(TWO_PLACES)
        net_margin_pct = round(float((net_operating_profit / net_sales) * 100), 1) if net_sales > ZERO else 0.0

        # Previous Period comparison
        prev_sales_q = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.coalesce(func.sum(Sale.refund_amount), 0)
        ).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= prev_start_dt,
            Sale.created_at <= prev_end_dt
        ).first()
        prev_net = max(to_dec(prev_sales_q[0]) - to_dec(prev_sales_q[1]), ZERO).quantize(TWO_PLACES)
        sales_growth_pct = calculate_percentage_change(net_sales, prev_net)

        return {
            "period_label": label,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "gross_sales": gross_sales,
            "refunds": refunds,
            "net_sales": net_sales,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin_pct,
            "operating_expenses": operating_expenses,
            "labor_cost": labor_cost,
            "total_operating_costs": total_operating_costs,
            "net_operating_profit": net_operating_profit,
            "net_margin_pct": net_margin_pct,
            "order_count": order_count,
            "aov": aov,
            "total_worked_hours": round(total_worked_hours, 2),
            "sales_growth_pct": sales_growth_pct,
        }

    # -------------------------------------------------------------
    # 2. Comprehensive Profit & Loss (P&L) Statement
    # -------------------------------------------------------------

    @staticmethod
    def get_profit_and_loss(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        # Sales aggregates
        sales_row = db.session.query(
            func.coalesce(func.sum(Sale.subtotal_amount), 0),
            func.coalesce(func.sum(Sale.tax_amount), 0),
            func.coalesce(func.sum(Sale.discount_amount), 0),
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.coalesce(func.sum(Sale.refund_amount), 0),
            func.count(Sale.id)
        ).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).first()

        subtotal = to_dec(sales_row[0]).quantize(TWO_PLACES)
        tax = to_dec(sales_row[1]).quantize(TWO_PLACES)
        discounts = to_dec(sales_row[2]).quantize(TWO_PLACES)
        gross_sales = to_dec(sales_row[3]).quantize(TWO_PLACES)
        refunds = to_dec(sales_row[4]).quantize(TWO_PLACES)
        orders_count = int(sales_row[5] or 0)
        net_revenue = max(gross_sales - refunds, ZERO).quantize(TWO_PLACES)

        # Cost of Goods Sold (COGS)
        cogs_val = db.session.query(
            func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0)
        ).join(Sale, Sale.id == SaleItem.sale_id).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).scalar()
        cogs = to_dec(cogs_val).quantize(TWO_PLACES)

        gross_profit = (net_revenue - cogs).quantize(TWO_PLACES)
        gross_margin_pct = round(float((gross_profit / net_revenue) * 100), 1) if net_revenue > ZERO else 0.0

        # Operating Expenses by Category
        categories = ExpenseCategory.query.filter_by(is_active=True).all()
        expense_lines = []
        total_overhead = ZERO

        for cat in categories:
            cat_sum = db.session.query(
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id)
            ).filter(
                Expense.category_id == cat.id,
                Expense.status == ExpenseStatus.RECORDED,
                Expense.expense_date >= start_dt.date(),
                Expense.expense_date <= end_dt.date()
            ).first()

            amount = to_dec(cat_sum[0]).quantize(TWO_PLACES)
            count = int(cat_sum[1] or 0)
            if amount > ZERO or count > 0:
                expense_lines.append({
                    "category_id": cat.id,
                    "category_name": cat.name,
                    "category_code": cat.code,
                    "amount": amount,
                    "count": count,
                })
                total_overhead += amount

        # Also check uncategorized / other recorded expenses
        uncat_sum = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id)
        ).filter(
            Expense.category_id == None,
            Expense.status == ExpenseStatus.RECORDED,
            Expense.expense_date >= start_dt.date(),
            Expense.expense_date <= end_dt.date()
        ).first()
        uncat_amt = to_dec(uncat_sum[0]).quantize(TWO_PLACES)
        if uncat_amt > ZERO:
            expense_lines.append({
                "category_id": 0,
                "category_name": "Other Uncategorized",
                "category_code": "OTHER",
                "amount": uncat_amt,
                "count": int(uncat_sum[1] or 0),
            })
            total_overhead += uncat_amt

        # Operating Labor Cost from Staff Attendance
        attendances = ShiftAttendance.query.filter(
            ShiftAttendance.clock_in >= start_dt,
            ShiftAttendance.clock_in <= end_dt
        ).all()
        labor_cost = ZERO
        total_hours = 0.0
        for att in attendances:
            rate = to_dec(att.employee_profile.hourly_rate if att.employee_profile else Decimal("15.00"))
            hrs = Decimal(str(round(att.total_hours, 2)))
            labor_cost += (rate * hrs)
            total_hours += att.total_hours
        labor_cost = labor_cost.quantize(TWO_PLACES)

        total_operating_expenses = (total_overhead + labor_cost).quantize(TWO_PLACES)
        net_operating_income = (gross_profit - total_operating_expenses).quantize(TWO_PLACES)
        net_margin_pct = round(float((net_operating_income / net_revenue) * 100), 1) if net_revenue > ZERO else 0.0

        disclosure = (
            "Accounting Disclosure: This operational Income Statement reflects store-level cash & accrued sales, "
            "recipe bill-of-materials cost of goods sold, recorded store overhead expenses, and staff shift labor hours. "
            "Statutory corporate income tax, balance-sheet capital asset depreciation, and external payroll liabilities are handled outside this operational ledger."
        )

        return {
            "period_label": label,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "gross_sales": gross_sales,
            "refunds": refunds,
            "discounts": discounts,
            "subtotal": subtotal,
            "tax": tax,
            "net_revenue": net_revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin_pct,
            "expense_categories": expense_lines,
            "total_overhead": total_overhead.quantize(TWO_PLACES),
            "labor_cost": labor_cost,
            "total_hours": round(total_hours, 2),
            "total_operating_expenses": total_operating_expenses,
            "net_operating_income": net_operating_income,
            "net_margin_pct": net_margin_pct,
            "orders_count": orders_count,
            "disclosure": disclosure,
        }

    # -------------------------------------------------------------
    # 3. Product Sales & Gross Margin Analytics
    # -------------------------------------------------------------

    @staticmethod
    def get_product_performance(period="this_month", start_date=None, end_date=None, category_id=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        query = db.session.query(
            SaleItem.product_id,
            SaleItem.product_name,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("units_sold"),
            func.coalesce(func.sum(SaleItem.subtotal), 0).label("revenue"),
            func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0).label("cogs")
        ).join(Sale, Sale.id == SaleItem.sale_id).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        )

        if category_id:
            query = query.join(Product, Product.id == SaleItem.product_id).filter(Product.category_id == category_id)

        query = query.group_by(SaleItem.product_id, SaleItem.product_name).order_by(func.sum(SaleItem.subtotal).desc())
        rows = query.all()

        total_revenue = sum((to_dec(r[3]) for r in rows), ZERO)
        items = []

        for r in rows:
            prod_id = r[0]
            name = r[1]
            units = int(r[2])
            rev = to_dec(r[3]).quantize(TWO_PLACES)
            cogs = to_dec(r[4]).quantize(TWO_PLACES)
            margin = (rev - cogs).quantize(TWO_PLACES)
            margin_pct = round(float((margin / rev) * 100), 1) if rev > ZERO else 0.0
            rev_share = round(float((rev / total_revenue) * 100), 1) if total_revenue > ZERO else 0.0
            avg_price = (rev / Decimal(units)).quantize(TWO_PLACES) if units > 0 else ZERO

            # Get SKU & Category Name
            prod = db.session.get(Product, prod_id)
            sku = prod.sku if prod else ""
            cat_name = prod.category.name if prod and prod.category else "Uncategorized"

            items.append({
                "product_id": prod_id,
                "name": name,
                "sku": sku,
                "category_name": cat_name,
                "units_sold": units,
                "revenue": rev,
                "cogs": cogs,
                "gross_margin": margin,
                "margin_pct": margin_pct,
                "revenue_share": rev_share,
                "avg_price": avg_price,
            })

        return {
            "period_label": label,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "total_products_sold": sum(i["units_sold"] for i in items),
            "total_revenue": total_revenue.quantize(TWO_PLACES),
            "items": items,
            "products": items,
        }

    # -------------------------------------------------------------
    # 4. Category Mix Performance
    # -------------------------------------------------------------

    @staticmethod
    def get_category_performance(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        query = db.session.query(
            Category.id,
            Category.name,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("units_sold"),
            func.coalesce(func.sum(SaleItem.subtotal), 0).label("revenue")
        ).join(Product, Product.category_id == Category.id)\
         .join(SaleItem, SaleItem.product_id == Product.id)\
         .join(Sale, Sale.id == SaleItem.sale_id)\
         .filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
         ).group_by(Category.id, Category.name).order_by(func.sum(SaleItem.subtotal).desc())

        rows = query.all()
        total_rev = sum((to_dec(r[3]) for r in rows), ZERO)

        categories = []
        for r in rows:
            rev = to_dec(r[3]).quantize(TWO_PLACES)
            share = round(float((rev / total_rev) * 100), 1) if total_rev > ZERO else 0.0
            categories.append({
                "category_id": r[0],
                "name": r[1],
                "units_sold": int(r[2]),
                "revenue": rev,
                "revenue_share": share,
            })

        return {
            "period_label": label,
            "total_revenue": total_rev.quantize(TWO_PLACES),
            "categories": categories,
        }

    # -------------------------------------------------------------
    # 5. Payment Methods Breakdown
    # -------------------------------------------------------------

    @staticmethod
    def get_payment_methods(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        query = db.session.query(
            Sale.payment_method,
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).group_by(Sale.payment_method).all()

        total_amount = sum((to_dec(r[2]) for r in query), ZERO)
        methods = []

        for r in query:
            amt = to_dec(r[2]).quantize(TWO_PLACES)
            share = round(float((amt / total_amount) * 100), 1) if total_amount > ZERO else 0.0
            methods.append({
                "method": r[0],
                "transactions": int(r[1]),
                "amount": amt,
                "share_pct": share,
            })

        return {
            "period_label": label,
            "total_amount": total_amount.quantize(TWO_PLACES),
            "methods": methods,
        }

    # -------------------------------------------------------------
    # 6. POS Register Shift Audit
    # -------------------------------------------------------------

    @staticmethod
    def get_pos_register_audits(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        shifts = POSRegisterShift.query.filter(
            POSRegisterShift.opened_at >= start_dt,
            POSRegisterShift.opened_at <= end_dt
        ).order_by(POSRegisterShift.opened_at.desc()).all()

        total_sales = sum((to_dec(s.total_sales_amount) for s in shifts), ZERO)
        total_orders = sum(s.total_orders_count for s in shifts)
        total_discrepancy = sum((to_dec(s.discrepancy) for s in shifts), ZERO)

        shift_items = []
        for s in shifts:
            shift_items.append({
                "id": s.id,
                "cashier_name": s.user.full_name if s.user else "Unknown",
                "opened_at": s.opened_at.strftime("%Y-%m-%d %H:%M"),
                "closed_at": s.closed_at.strftime("%Y-%m-%d %H:%M") if s.closed_at else None,
                "opening_cash": to_dec(s.opening_cash).quantize(TWO_PLACES),
                "closing_cash": to_dec(s.closing_cash).quantize(TWO_PLACES) if s.closing_cash is not None else None,
                "expected_cash": to_dec(s.expected_cash).quantize(TWO_PLACES) if s.expected_cash is not None else None,
                "discrepancy": to_dec(s.discrepancy).quantize(TWO_PLACES),
                "total_sales": to_dec(s.total_sales_amount).quantize(TWO_PLACES),
                "order_count": s.total_orders_count,
                "is_active": s.is_active,
                "notes": s.notes or "",
            })

        return {
            "period_label": label,
            "total_shifts": len(shifts),
            "total_sales": total_sales.quantize(TWO_PLACES),
            "total_orders": total_orders,
            "total_discrepancy": total_discrepancy.quantize(TWO_PLACES),
            "shifts": shift_items,
        }

    # -------------------------------------------------------------
    # 7. Raw Material Inventory, COGS & Valuation
    # -------------------------------------------------------------

    @staticmethod
    def get_inventory_valuation_and_cogs(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        items = Ingredient.query.filter_by(is_active=True).all()
        total_valuation = ZERO
        low_stock_count = 0
        out_of_stock_count = 0

        inventory_rows = []
        for it in items:
            val = (to_dec(it.current_quantity) * to_dec(it.cost_per_unit)).quantize(TWO_PLACES)
            total_valuation += val
            if it.is_out_of_stock:
                out_of_stock_count += 1
            elif it.is_low_stock:
                low_stock_count += 1

            inventory_rows.append({
                "id": it.id,
                "name": it.name,
                "sku": it.sku,
                "category": it.category.name if it.category else "Ingredients",
                "current_quantity": float(it.current_quantity),
                "unit": it.unit_of_measure.code if it.unit_of_measure else it.unit,
                "cost_per_unit": to_dec(it.cost_per_unit).quantize(Decimal("0.0001")),
                "valuation": val,
                "stock_status": it.stock_status,
            })

        # Purchases in this period
        purchases_sum = db.session.query(
            func.coalesce(func.sum(Purchase.total_cost), 0)
        ).filter(
            Purchase.status == PurchaseStatus.RECEIVED,
            Purchase.purchase_date >= start_dt,
            Purchase.purchase_date <= end_dt
        ).scalar()
        total_purchases = to_dec(purchases_sum).quantize(TWO_PLACES)

        # Recipe COGS in this period
        cogs_val = db.session.query(
            func.coalesce(func.sum(SaleItem.unit_cost * SaleItem.quantity), 0)
        ).join(Sale, Sale.id == SaleItem.sale_id).filter(
            Sale.status.in_([SaleStatus.COMPLETED, SaleStatus.PARTIALLY_REFUNDED]),
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt
        ).scalar()
        cogs_consumed = to_dec(cogs_val).quantize(TWO_PLACES)

        return {
            "period_label": label,
            "total_items": len(items),
            "total_valuation": total_valuation.quantize(TWO_PLACES),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "total_purchases": total_purchases,
            "cogs_consumed": cogs_consumed,
            "items": inventory_rows,
            "inventory_items": inventory_rows,
        }

    # -------------------------------------------------------------
    # 8. Staff Labor & Attendance Report
    # -------------------------------------------------------------

    @staticmethod
    def get_staff_labor_report(period="this_month", start_date=None, end_date=None):
        start_dt, end_dt, label = get_date_range_bounds(period, start_date, end_date)

        profiles = EmployeeProfile.query.all()
        staff_data = []
        overall_hours = 0.0
        overall_labor_cost = ZERO

        for prof in profiles:
            attendances = ShiftAttendance.query.filter(
                ShiftAttendance.employee_id == prof.id,
                ShiftAttendance.clock_in >= start_dt,
                ShiftAttendance.clock_in <= end_dt
            ).all()

            shifts_count = len(attendances)
            hours = sum(a.total_hours for a in attendances)
            rate = to_dec(prof.hourly_rate or Decimal("15.00"))
            wages = (rate * to_dec(round(hours, 2))).quantize(TWO_PLACES)

            late_shifts = sum(1 for a in attendances if a.late_minutes > 0 or a.status == AttendanceStatus.LATE)
            on_time_shifts = shifts_count - late_shifts
            on_time_pct = round((on_time_shifts / shifts_count * 100), 1) if shifts_count > 0 else 100.0

            overall_hours += hours
            overall_labor_cost += wages

            if shifts_count > 0 or prof.employment_status == "ACTIVE":
                staff_data.append({
                    "profile_id": prof.id,
                    "employee_code": prof.employee_code,
                    "name": prof.full_name,
                    "position": prof.position,
                    "status": prof.employment_status,
                    "hourly_rate": rate,
                    "total_shifts": shifts_count,
                    "total_hours": round(hours, 2),
                    "on_time_pct": on_time_pct,
                    "late_shifts": late_shifts,
                    "estimated_wages": wages,
                })

        return {
            "period_label": label,
            "total_staff_active": len(profiles),
            "overall_hours": round(overall_hours, 2),
            "overall_labor_cost": overall_labor_cost.quantize(TWO_PLACES),
            "staff": staff_data,
        }

    # -------------------------------------------------------------
    # Backward Compatibility
    # -------------------------------------------------------------

    @staticmethod
    def get_financial_summary(start_date=None, end_date=None):
        return ReportService.get_executive_kpis(period="custom", start_date=start_date, end_date=end_date)

    @staticmethod
    def get_sales_by_payment_method(start_date=None, end_date=None):
        res = ReportService.get_payment_methods(period="custom", start_date=start_date, end_date=end_date)
        return [{"method": m["method"], "orders": m["transactions"], "total": float(m["amount"])} for m in res["methods"]]
