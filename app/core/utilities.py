import uuid
from datetime import datetime


def generate_invoice_number(prefix="INV"):
    """Generate a unique human-readable invoice or order receipt number."""
    now_str = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{now_str}-{unique_suffix}"


def generate_expense_number(prefix="EXP"):
    """Generate a unique human-readable expense reference number."""
    now_str = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{now_str}-{unique_suffix}"


def generate_sku(category_code="GEN", product_name=""):
    """Generate a unique SKU code based on product name and timestamp."""
    clean_name = "".join(c for c in product_name.upper() if c.isalnum())[:4]
    random_part = uuid.uuid4().hex[:4].upper()
    return f"{category_code[:3].upper()}-{clean_name or 'ITEM'}-{random_part}"


def format_currency(amount, symbol="₱"):
    """Format a numeric value into a currency string (e.g., ₱12.50)."""
    try:
        if amount is None or str(amount).strip() == "":
            return f"{symbol}0.00"
        return f"{symbol}{float(amount):,.2f}"
    except (ValueError, TypeError, Exception):
        return f"{symbol}0.00"


def format_datetime(dt, fmt="%b %d, %Y %I:%M %p"):
    """Format a datetime object into readable string."""
    if not dt:
        return ""
    return dt.strftime(fmt)


def generate_employee_code(seq_num: int) -> str:
    """Generate standardized employee code, e.g. EMP-0042."""
    return f"EMP-{int(seq_num):04d}"


def calculate_percentage_change(current, previous) -> float:
    """Calculate percentage growth between two Decimal or float values."""
    from decimal import Decimal
    c = Decimal(str(current or 0))
    p = Decimal(str(previous or 0))
    if p == 0:
        if c > 0:
            return 100.0
        elif c < 0:
            return -100.0
        return 0.0
    change = ((c - p) / abs(p)) * 100
    return round(float(change), 1)


def get_date_range_bounds(period_code="this_month", start_date=None, end_date=None):
    """
    Calculate datetime bounds for reporting periods.
    Returns (start_datetime, end_datetime, label).
    """
    from datetime import date, timedelta
    import calendar

    today = date.today()

    if period_code == "today":
        start_d = today
        end_d = today
        label = f"Today ({today.strftime('%b %d, %Y')})"
    elif period_code == "yesterday":
        start_d = today - timedelta(days=1)
        end_d = start_d
        label = f"Yesterday ({start_d.strftime('%b %d, %Y')})"
    elif period_code == "this_week":
        start_d = today - timedelta(days=today.weekday())  # Monday
        end_d = start_d + timedelta(days=6)
        label = f"This Week ({start_d.strftime('%b %d')} - {end_d.strftime('%b %d, %Y')})"
    elif period_code == "last_week":
        this_mon = today - timedelta(days=today.weekday())
        start_d = this_mon - timedelta(days=7)
        end_d = start_d + timedelta(days=6)
        label = f"Last Week ({start_d.strftime('%b %d')} - {end_d.strftime('%b %d, %Y')})"
    elif period_code == "this_month":
        start_d = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_d = date(today.year, today.month, last_day)
        label = f"This Month ({today.strftime('%B %Y')})"
    elif period_code == "last_month":
        first_of_this_month = date(today.year, today.month, 1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        start_d = date(last_of_prev_month.year, last_of_prev_month.month, 1)
        end_d = last_of_prev_month
        label = f"Last Month ({last_of_prev_month.strftime('%B %Y')})"
    elif period_code == "this_quarter":
        quarter = (today.month - 1) // 3 + 1
        first_month = 3 * (quarter - 1) + 1
        last_month = first_month + 2
        start_d = date(today.year, first_month, 1)
        last_day = calendar.monthrange(today.year, last_month)[1]
        end_d = date(today.year, last_month, last_day)
        label = f"Q{quarter} {today.year}"
    elif period_code == "this_year":
        start_d = date(today.year, 1, 1)
        end_d = date(today.year, 12, 31)
        label = f"Year {today.year}"
    elif period_code == "custom" and start_date and end_date:
        try:
            if isinstance(start_date, str):
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            else:
                start_d = start_date
            if isinstance(end_date, str):
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_d = end_date
            label = f"{start_d.strftime('%b %d, %Y')} - {end_d.strftime('%b %d, %Y')}"
        except (ValueError, TypeError):
            start_d = date(today.year, today.month, 1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_d = date(today.year, today.month, last_day)
            label = f"This Month ({today.strftime('%B %Y')})"
    else:
        # Default fallback to this month
        start_d = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_d = date(today.year, today.month, last_day)
        label = f"This Month ({today.strftime('%B %Y')})"

    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d, datetime.max.time())
    return start_dt, end_dt, label

