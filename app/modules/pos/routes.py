from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.core.decorators import roles_required
from app.core.permissions import Roles
from app.modules.pos.services import POSService
from app.modules.catalog.services import CatalogService
from app.modules.sales.models import Sale
from app.extensions import db
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException
from app.core.utilities import format_currency

pos_bp = Blueprint("pos", __name__)


@pos_bp.route("/", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.BARISTA, Roles.CASHIER)
def index():
    categories = CatalogService.get_categories(active_only=True)
    products = CatalogService.get_products_paginated(page=1, per_page=200, available_only=True).items
    active_shift = POSService.get_active_shift(current_user.id)
    tax_rate = current_app.config.get("TAX_RATE", 0.08)
    option_groups = CatalogService.get_option_groups(active_only=True)

    products_json = [p.to_dict() for p in products]
    option_groups_json = [g.to_dict() for g in option_groups]

    return render_template(
        "pos/index.html",
        categories=categories,
        products=products,
        products_json=products_json,
        active_shift=active_shift,
        tax_rate=tax_rate,
        option_groups=option_groups,
        option_groups_json=option_groups_json
    )


@pos_bp.route("/shift/open", methods=["POST"])
@login_required
def open_shift():
    data = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        opening_cash = float(data.get("opening_cash", 0.0) or 0.0)
        notes = data.get("notes", "")
        shift = POSService.open_shift(current_user.id, opening_cash, notes)

        if request.is_json:
            return api_success(shift.to_dict(), message="Shift opened successfully")

        flash("Register shift opened. Ready to take orders!", "success")
    except AppException as e:
        if request.is_json:
            return api_error(e.message, e.status_code)
        flash(e.message, "danger")

    return redirect(url_for("pos.index"))


@pos_bp.route("/shift/close", methods=["POST"])
@login_required
def close_shift():
    data = request.form if request.form else (request.get_json(silent=True) or {})
    shift_id = data.get("shift_id")
    try:
        closing_cash = float(data.get("closing_cash", 0.0) or 0.0)
        notes = data.get("notes", "")
        shift = POSService.close_shift(int(shift_id), closing_cash, notes)

        if request.is_json:
            return api_success(shift.to_dict(), message="Shift closed successfully")

        flash(f"Register shift closed. Discrepancy: {format_currency(shift.discrepancy)}", "info")
    except AppException as e:
        if request.is_json:
            return api_error(e.message, e.status_code)
        flash(e.message, "danger")

    return redirect(url_for("pos.index"))


@pos_bp.route("/checkout", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER, Roles.BARISTA, Roles.CASHIER)
def checkout():
    data = request.get_json(silent=True)
    if not data:
        return api_error("Invalid checkout payload", 400)

    try:
        tax_rate = current_app.config.get("TAX_RATE", 0.08)
        idempotency_key = data.get("idempotency_key") or request.headers.get("X-Idempotency-Key")
        sale = POSService.checkout(
            user_id=current_user.id,
            items_data=data.get("items", []),
            payment_method=data.get("payment_method", "Cash"),
            cash_tendered=data.get("cash_tendered", 0.0),
            customer_name=data.get("customer_name", "Guest"),
            discount_amount=data.get("discount_amount", 0.0),
            notes=data.get("notes", ""),
            tax_rate=tax_rate,
            idempotency_key=idempotency_key
        )
        return api_success(sale.to_dict(), message=f"Order {sale.invoice_no} completed successfully!")
    except AppException as e:
        return api_error(e.message, e.status_code)


@pos_bp.route("/receipt/<int:sale_id>", methods=["GET"])
@login_required
def receipt(sale_id):
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found", "danger")
        return redirect(url_for("pos.index"))
    return render_template("sales/receipt.html", sale=sale)


@pos_bp.route("/api/shift/status", methods=["GET"])
@login_required
def shift_status():
    shift = POSService.get_active_shift(current_user.id)
    return api_success({
        "has_active_shift": shift is not None,
        "shift": shift.to_dict() if shift else None
    })

