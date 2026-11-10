from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.core.decorators import roles_required
from app.core.permissions import Roles
from app.modules.expenses.services import ExpenseService
from app.modules.expenses.models import ExpenseStatus, ExpensePaymentMethod
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException

expenses_bp = Blueprint("expenses", __name__)


@expenses_bp.route("/", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def index():
    page = request.args.get("page", 1, type=int)
    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", "").strip()
    payment_method = request.args.get("payment_method", "").strip()
    search = request.args.get("q", "").strip()
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

    pagination = ExpenseService.get_expenses_paginated(
        page=page,
        per_page=15,
        category_id=category_id,
        status=status if status else None,
        payment_method=payment_method if payment_method else None,
        date_from=date_from,
        date_to=date_to,
        search=search if search else None
    )

    categories = ExpenseService.get_categories()
    summary = ExpenseService.get_expense_summary(date_from=date_from, date_to=date_to, category_id=category_id)
    breakdown = ExpenseService.get_category_breakdown(date_from=date_from, date_to=date_to)

    return render_template(
        "expenses/index.html",
        pagination=pagination,
        categories=categories,
        summary=summary,
        breakdown=breakdown,
        selected_category_id=category_id,
        selected_status=status,
        selected_payment_method=payment_method,
        search=search,
        start_date=start_str,
        end_date=end_str,
        statuses=ExpenseStatus.ALL,
        payment_methods=ExpensePaymentMethod.ALL
    )


@expenses_bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def create():
    if request.method == "POST":
        data = request.form
        date_str = data.get("expense_date", "").strip()
        exp_date = None
        if date_str:
            try:
                exp_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        try:
            exp = ExpenseService.create_expense(
                title=data.get("title", ""),
                category_id=data.get("category_id"),
                amount=data.get("amount"),
                expense_date=exp_date,
                payment_method=data.get("payment_method", "Cash"),
                vendor_payee=data.get("vendor_payee", ""),
                notes=data.get("notes", ""),
                user_id=current_user.id
            )
            flash(f"Expense #{exp.expense_number} logged successfully.", "success")
            return redirect(url_for("expenses.index"))
        except AppException as e:
            flash(e.message, "danger")

    categories = ExpenseService.get_categories(active_only=True)
    return render_template(
        "expenses/form.html",
        categories=categories,
        payment_methods=ExpensePaymentMethod.ALL,
        expense=None
    )


@expenses_bp.route("/<int:expense_id>", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def detail(expense_id):
    expense = ExpenseService.get_expense_by_id(expense_id)
    return render_template("expenses/detail.html", expense=expense)


@expenses_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def edit(expense_id):
    expense = ExpenseService.get_expense_by_id(expense_id)

    if request.method == "POST":
        data = request.form
        date_str = data.get("expense_date", "").strip()
        exp_date = None
        if date_str:
            try:
                exp_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        try:
            ExpenseService.update_expense(
                expense_id=expense.id,
                title=data.get("title", ""),
                category_id=data.get("category_id"),
                amount=data.get("amount"),
                expense_date=exp_date,
                payment_method=data.get("payment_method", "Cash"),
                vendor_payee=data.get("vendor_payee", ""),
                notes=data.get("notes", ""),
                user_id=current_user.id
            )
            flash(f"Expense #{expense.expense_number} updated successfully.", "success")
            return redirect(url_for("expenses.detail", expense_id=expense.id))
        except AppException as e:
            flash(e.message, "danger")

    categories = ExpenseService.get_categories(active_only=True)
    return render_template(
        "expenses/form.html",
        expense=expense,
        categories=categories,
        payment_methods=ExpensePaymentMethod.ALL
    )


@expenses_bp.route("/<int:expense_id>/void", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def void(expense_id):
    reason = request.form.get("reason", "").strip()
    try:
        exp = ExpenseService.void_expense(expense_id, reason=reason, user_id=current_user.id)
        flash(f"Expense #{exp.expense_number} has been voided.", "warning")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(url_for("expenses.detail", expense_id=expense_id))


@expenses_bp.route("/<int:expense_id>/delete", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def delete(expense_id):
    # Backward compatibility: void instead of delete
    try:
        ExpenseService.void_expense(expense_id, reason="Voided via delete button", user_id=current_user.id)
        flash("Expense record marked as voided.", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("expenses.index"))


@expenses_bp.route("/categories", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        try:
            cat = ExpenseService.create_category(name=name, code=code, description=description, user_id=current_user.id)
            flash(f"Expense category '{cat.name}' [{cat.code}] created successfully.", "success")
            return redirect(url_for("expenses.categories"))
        except AppException as e:
            flash(e.message, "danger")

    cats = ExpenseService.get_categories()
    return render_template("expenses/categories.html", categories=cats)


@expenses_bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def toggle_category(category_id):
    cat = ExpenseService.get_category_by_id(category_id)
    new_state = not cat.is_active
    ExpenseService.update_category(
        category_id=cat.id,
        name=cat.name,
        code=cat.code,
        description=cat.description,
        is_active=new_state,
        user_id=current_user.id
    )
    status_str = "activated" if new_state else "deactivated"
    flash(f"Category '{cat.name}' has been {status_str}.", "info")
    return redirect(url_for("expenses.categories"))


@expenses_bp.route("/api/<int:expense_id>", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def api_expense(expense_id):
    exp = ExpenseService.get_expense_by_id(expense_id)
    return api_success(exp.to_dict())
