from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.core.decorators import roles_required
from app.core.permissions import Roles
from app.modules.sales.services import SalesService
from app.modules.sales.models import SaleStatus, PaymentMethod
from app.modules.users.models import User
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException

sales_bp = Blueprint("sales", __name__)


@sales_bp.route("/", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER, Roles.STAFF)
def index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    payment_method = request.args.get("payment_method", "").strip()
    cashier_id = request.args.get("cashier_id", type=int)
    shift_id = request.args.get("shift_id", type=int)
    start_str = request.args.get("start_date", "").strip()
    end_str = request.args.get("end_date", "").strip()

    date_from = None
    date_to = None
    if start_str:
        try:
            date_from = datetime.strptime(start_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    if end_str:
        try:
            date_to = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    pagination = SalesService.get_sales_paginated(
        page=page,
        per_page=15,
        date_from=date_from,
        date_to=date_to,
        search=search if search else None,
        status=status if status else None,
        payment_method=payment_method if payment_method else None,
        cashier_id=cashier_id,
        shift_id=shift_id
    )

    summary = SalesService.get_sales_summary(
        date_from=date_from,
        date_to=date_to,
        cashier_id=cashier_id,
        shift_id=shift_id
    )

    cashiers = User.query.filter(User.is_active == True).order_by(User.first_name.asc()).all()

    return render_template(
        "sales/index.html",
        pagination=pagination,
        summary=summary,
        search=search,
        selected_status=status,
        selected_payment_method=payment_method,
        selected_cashier_id=cashier_id,
        selected_shift_id=shift_id,
        start_date=start_str,
        end_date=end_str,
        cashiers=cashiers,
        statuses=SaleStatus.ALL,
        payment_methods=PaymentMethod.ALL
    )


@sales_bp.route("/<int:sale_id>", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER, Roles.STAFF)
def detail(sale_id):
    sale = SalesService.get_sale_by_id(sale_id)
    return render_template("sales/detail.html", sale=sale)


@sales_bp.route("/<int:sale_id>/receipt", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.CASHIER, Roles.STAFF)
def receipt(sale_id):
    sale = SalesService.get_sale_by_id(sale_id)
    SalesService.record_receipt_reprint(sale_id, user_id=current_user.id, ip_address=request.remote_addr)
    return render_template("sales/receipt.html", sale=sale)


@sales_bp.route("/<int:sale_id>/refund", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def refund(sale_id):
    reason = request.form.get("reason", "").strip()
    amount_str = request.form.get("amount", "").strip()

    refund_amt = None
    if amount_str:
        try:
            refund_amt = float(amount_str)
        except ValueError:
            flash("Invalid refund amount format.", "danger")
            return redirect(url_for("sales.detail", sale_id=sale_id))

    try:
        sale = SalesService.refund_sale(sale_id, refund_amount=refund_amt, reason=reason, user_id=current_user.id)
        flash(f"Order #{sale.invoice_no} refund processed successfully.", "success")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(url_for("sales.detail", sale_id=sale_id))


@sales_bp.route("/<int:sale_id>/void", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def void(sale_id):
    reason = request.form.get("reason", "").strip()
    try:
        sale = SalesService.void_sale(sale_id, reason=reason, user_id=current_user.id)
        flash(f"Order #{sale.invoice_no} has been voided.", "warning")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(url_for("sales.detail", sale_id=sale_id))


@sales_bp.route("/api/<int:sale_id>", methods=["GET"])
@login_required
def api_sale(sale_id):
    sale = SalesService.get_sale_by_id(sale_id)
    return api_success(sale.to_dict())


@sales_bp.route("/api/summary", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def api_summary():
    start_str = request.args.get("start_date", "").strip()
    end_str = request.args.get("end_date", "").strip()
    date_from = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else None
    date_to = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else None

    summary = SalesService.get_sales_summary(date_from=date_from, date_to=date_to)
    # Serialize Decimals to float for JSON response
    res = {k: float(v) if hasattr(v, "quantize") else v for k, v in summary.items()}
    return api_success(res)
