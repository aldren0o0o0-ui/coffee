from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.core.decorators import roles_required, permission_required
from app.core.permissions import Roles, Permissions
from app.modules.users.services import UserService
from app.core.exceptions import AppException

users_bp = Blueprint("users", __name__)


@users_bp.route("/", methods=["GET"])
@login_required
@permission_required(Permissions.USERS_VIEW)
def index():
    page = request.args.get("page", 1, type=int)
    role = request.args.get("role", "")
    is_active = request.args.get("is_active", "")
    search = request.args.get("q", "")

    pagination = UserService.get_users_paginated(
        page=page, per_page=15, role=role if role else None, is_active=is_active if is_active != "" else None, search=search
    )
    return render_template(
        "users/index.html",
        pagination=pagination,
        roles=Roles.ALL,
        selected_role=role,
        selected_active=is_active,
        search=search
    )


@users_bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.USERS_CREATE)
def create():
    if request.method == "POST":
        data = request.form
        ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)

        try:
            user = UserService.create_user(
                username=data.get("username"),
                email=data.get("email"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                password=data.get("password"),
                role=data.get("role", Roles.STAFF),
                is_active="is_active" in data,
                actor=current_user,
                ip_address=ip_addr
            )
            flash(f"Staff account '{user.username}' created successfully.", "success")
            return redirect(url_for("users.index"))
        except AppException as e:
            flash(e.message, "danger")

    # Only OWNER can assign OWNER role
    assignable_roles = Roles.ALL if current_user.is_owner else [r for r in Roles.ALL if r != Roles.OWNER]
    return render_template("users/create.html", roles=assignable_roles)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.USERS_UPDATE)
def edit(user_id):
    user = UserService.get_user_by_id(user_id)
    ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)

    if request.method == "POST":
        data = request.form
        try:
            UserService.update_user(
                user_id=user.id,
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=data.get("email"),
                role=data.get("role"),
                is_active="is_active" in data,
                password=data.get("password"),
                actor=current_user,
                ip_address=ip_addr
            )
            flash("Staff account details updated successfully.", "success")
            return redirect(url_for("users.index"))
        except AppException as e:
            flash(e.message, "danger")

    assignable_roles = Roles.ALL if current_user.is_owner else [r for r in Roles.ALL if r != Roles.OWNER]
    return render_template("users/edit.html", user=user, roles=assignable_roles)


@users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@permission_required(Permissions.USERS_DEACTIVATE)
def toggle_status(user_id):
    ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
    try:
        user = UserService.toggle_user_status(user_id, actor=current_user, ip_address=ip_addr)
        status_text = "activated" if user.is_active else "deactivated"
        flash(f"Staff account '{user.username}' has been {status_text}.", "info")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(url_for("users.index"))
