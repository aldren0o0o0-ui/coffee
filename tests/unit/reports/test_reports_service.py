import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from app.extensions import db
from app.modules.sales.models import Sale, SaleItem, SaleStatus
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus
from app.modules.inventory.models import Ingredient, Purchase, PurchaseStatus
from app.modules.pos.models import POSRegisterShift
from app.modules.employees.models import EmployeeProfile, ShiftAttendance, AttendanceStatus
from app.modules.reports.services import ReportService


@pytest.fixture
def setup_reporting_data(app, sample_catalog, staff_user, manager_user):
    """Setup comprehensive financial dataset for testing reporting engine."""
    today = date.today()
    prod = sample_catalog["product"]
    cat = sample_catalog["category"]

    # 1. POS Register Shift
    pos_shift = POSRegisterShift(
        user_id=staff_user.id,
        opening_cash=Decimal("100.00"),
        closing_cash=Decimal("250.00"),
        expected_cash=Decimal("250.00"),
        total_sales_amount=Decimal("150.00"),
        total_orders_count=2,
        opened_at=datetime.combine(today, time(8, 0)),
        closed_at=datetime.combine(today, time(16, 0)),
        is_active=False,
    )
    db.session.add(pos_shift)
    db.session.flush()

    # 2. Completed Sales with COGS
    sale1 = Sale(
        invoice_no="INV-REP-001",
        user_id=staff_user.id,
        shift_id=pos_shift.id,
        customer_name="Alice",
        subtotal_amount=Decimal("20.00"),
        tax_amount=Decimal("1.60"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("21.60"),
        refund_amount=Decimal("0.00"),
        payment_method="Card",
        status=SaleStatus.COMPLETED,
        created_at=datetime.combine(today, time(9, 30)),
    )
    db.session.add(sale1)
    db.session.flush()

    item1 = SaleItem(
        sale_id=sale1.id,
        product_id=prod.id,
        product_name=prod.name,
        quantity=4,
        unit_price=Decimal("5.00"),
        unit_cost=Decimal("1.25"),  # Total COGS: 4 * 1.25 = 5.00
        subtotal=Decimal("20.00"),
    )
    db.session.add(item1)

    # Sale 2: With partial refund
    sale2 = Sale(
        invoice_no="INV-REP-002",
        user_id=staff_user.id,
        shift_id=pos_shift.id,
        customer_name="Bob",
        subtotal_amount=Decimal("30.00"),
        tax_amount=Decimal("2.40"),
        discount_amount=Decimal("2.00"),
        total_amount=Decimal("30.40"),
        refund_amount=Decimal("10.00"),  # $10 refunded
        payment_method="Cash",
        status=SaleStatus.PARTIALLY_REFUNDED,
        created_at=datetime.combine(today, time(11, 0)),
    )
    db.session.add(sale2)
    db.session.flush()

    item2 = SaleItem(
        sale_id=sale2.id,
        product_id=prod.id,
        product_name=prod.name,
        quantity=6,
        unit_price=Decimal("5.00"),
        unit_cost=Decimal("1.25"),  # Total COGS: 6 * 1.25 = 7.50
        subtotal=Decimal("30.00"),
    )
    db.session.add(item2)

    # 3. Operating Expense
    exp_cat = ExpenseCategory(name="Shop Utilities", code="UTIL", is_active=True)
    db.session.add(exp_cat)
    db.session.flush()

    exp = Expense(
        expense_number="EXP-REP-001",
        title="Monthly Electricity",
        category_id=exp_cat.id,
        amount=Decimal("15.00"),
        expense_date=today,
        status=ExpenseStatus.RECORDED,
        recorded_by_id=manager_user.id,
    )
    db.session.add(exp)

    # 4. Staff Attendance (Labor Cost)
    prof = EmployeeProfile.query.filter_by(user_id=staff_user.id).first()
    if not prof:
        prof = EmployeeProfile(
            user_id=staff_user.id,
            employee_code="EMP-0010",
            position="Barista",
            hourly_rate=Decimal("20.00"),
        )
        db.session.add(prof)
        db.session.flush()
    else:
        prof.hourly_rate = Decimal("20.00")

    att = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=prof.id,
        attendance_date=today,
        clock_in=datetime.combine(today, time(8, 0)),
        clock_out=datetime.combine(today, time(10, 0)),  # 2.0 hours = $40.00 labor
        total_hours=2.0,
        worked_minutes=120,
        status=AttendanceStatus.PRESENT,
    )
    db.session.add(att)

    db.session.commit()
    return {"pos_shift": pos_shift, "prod": prod, "cat": cat}


def test_profit_and_loss_arithmetic_integrity(app, setup_reporting_data):
    """
    Test P&L calculations strictly preserve mathematical accounting identity:
    Gross Sales - Refunds = Net Sales
    Net Sales - COGS = Gross Profit
    Gross Profit - Operating Costs = Net Operating Profit
    """
    today = date.today()
    pnl = ReportService.get_profit_and_loss(period="today")

    # Gross Sales = 21.60 + 30.40 = 52.00
    assert pnl["gross_sales"] == Decimal("52.00")
    # Refunds = 10.00
    assert pnl["refunds"] == Decimal("10.00")
    # Net Revenue = 52.00 - 10.00 = 42.00
    assert pnl["net_revenue"] == Decimal("42.00")

    # COGS = 4 * 1.25 + 6 * 1.25 = 5.00 + 7.50 = 12.50
    assert pnl["cogs"] == Decimal("12.50")

    # Gross Profit = 42.00 - 12.50 = 29.50
    assert pnl["gross_profit"] == Decimal("29.50")
    # Margin % = (29.50 / 42.00) * 100 = 70.2%
    assert pnl["gross_margin_pct"] == 70.2

    # Overhead Expenses: $15.00
    assert pnl["total_overhead"] == Decimal("15.00")
    # Labor Cost: 2 hours @ $20.00 = $40.00
    assert pnl["labor_cost"] == Decimal("40.00")
    # Total Operating Expenses: 15.00 + 40.00 = 55.00
    assert pnl["total_operating_expenses"] == Decimal("55.00")

    # Net Operating Income: 29.50 - 55.00 = -25.50
    assert pnl["net_operating_income"] == Decimal("-25.50")

    # Disclosure must be present
    assert "Accounting Disclosure:" in pnl["disclosure"]
    assert "Statutory corporate income tax" in pnl["disclosure"]


def test_executive_kpis(app, setup_reporting_data):
    """Test executive KPI summary outputs."""
    kpis = ReportService.get_executive_kpis(period="today")
    assert kpis["gross_sales"] == Decimal("52.00")
    assert kpis["net_sales"] == Decimal("42.00")
    assert kpis["cogs"] == Decimal("12.50")
    assert kpis["gross_profit"] == Decimal("29.50")
    assert kpis["order_count"] == 2
    # AOV = 42.00 / 2 = 21.00
    assert kpis["aov"] == Decimal("21.00")


def test_product_and_category_performance(app, setup_reporting_data):
    """Test product sales velocity, margins, and category revenue share."""
    prod_data = ReportService.get_product_performance(period="today")
    assert prod_data["total_products_sold"] == 10  # 4 + 6 units
    assert len(prod_data["items"]) == 1

    item = prod_data["items"][0]
    assert item["units_sold"] == 10
    assert item["revenue"] == Decimal("50.00")  # 20.00 + 30.00 subtotal
    assert item["cogs"] == Decimal("12.50")
    assert item["gross_margin"] == Decimal("37.50")
    assert item["margin_pct"] == 75.0


def test_payment_methods_breakdown(app, setup_reporting_data):
    """Test payment method volume and share calculations."""
    pm = ReportService.get_payment_methods(period="today")
    assert len(pm["methods"]) == 2  # Cash and Card
    methods_dict = {m["method"]: m for m in pm["methods"]}

    assert "Card" in methods_dict
    assert "Cash" in methods_dict
    assert methods_dict["Card"]["transactions"] == 1
    assert methods_dict["Cash"]["transactions"] == 1


def test_pos_register_audits(app, setup_reporting_data):
    """Test POS register shift drawer reconciliation report."""
    audits = ReportService.get_pos_register_audits(period="today")
    assert audits["total_shifts"] == 1
    shift = audits["shifts"][0]
    assert shift["opening_cash"] == Decimal("100.00")
    assert shift["expected_cash"] == Decimal("250.00")
    assert shift["closing_cash"] == Decimal("250.00")
    assert shift["discrepancy"] == Decimal("0.00")


def test_staff_labor_report(app, setup_reporting_data):
    """Test staff labor analytics and wages estimation."""
    labor = ReportService.get_staff_labor_report(period="today")
    assert labor["overall_hours"] == 2.0
    assert labor["overall_labor_cost"] == Decimal("40.00")
    assert len(labor["staff"]) >= 1
