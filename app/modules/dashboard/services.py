from datetime import datetime, date, time
from sqlalchemy import func, desc
from app.extensions import db
from app.modules.sales.models import Sale, SaleItem, SaleStatus
from app.modules.inventory.models import Ingredient
from app.modules.expenses.models import Expense
from app.modules.catalog.models import Product


class DashboardService:
    @staticmethod
    def get_summary_metrics():
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        # 1. Today's Gross Sales
        today_sales_query = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0.0),
            func.count(Sale.id)
        ).filter(
            Sale.created_at >= today_start,
            Sale.created_at <= today_end,
            Sale.status == SaleStatus.COMPLETED
        ).first()

        today_revenue = float(today_sales_query[0])
        today_order_count = int(today_sales_query[1])

        # 2. Total active products count
        active_products_count = Product.query.filter_by(is_available=True).count()

        # 3. Low stock count
        low_stock_count = Ingredient.query.filter(Ingredient.current_stock <= Ingredient.minimum_stock).count()

        # 4. Today's Expenses
        today_expenses = float(db.session.query(
            func.coalesce(func.sum(Expense.amount), 0.0)
        ).filter(Expense.expense_date == date.today()).scalar())

        # 5. Recent 6 sales
        recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(6).all()

        # 6. Top 5 selling products (by volume)
        top_products = db.session.query(
            SaleItem.product_name,
            func.sum(SaleItem.quantity).label("total_qty"),
            func.sum(SaleItem.subtotal).label("total_revenue")
        ).join(Sale, Sale.id == SaleItem.sale_id)\
         .filter(Sale.status == SaleStatus.COMPLETED)\
         .group_by(SaleItem.product_name)\
         .order_by(desc("total_qty"))\
         .limit(5).all()

        return {
            "today_revenue": today_revenue,
            "today_orders": today_order_count,
            "active_products_count": active_products_count,
            "low_stock_count": low_stock_count,
            "today_expenses": today_expenses,
            "recent_sales": recent_sales,
            "top_products": [
                {"name": tp[0], "quantity": int(tp[1]), "revenue": float(tp[2])}
                for tp in top_products
            ]
        }
