from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.modules.auth.services import AuthService
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException
from app.extensions import limiter

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        is_api = request.is_json or request.path.startswith("/api/")
        data = request.get_json(silent=True) if is_api else request.form

        identifier = data.get("username", "") or data.get("email", "")
        password = data.get("password", "")
        remember = bool(data.get("remember", False))

        ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "")

        try:
            user = AuthService.authenticate(
                identifier=identifier,
                password=password,
                ip_address=ip_addr,
                user_agent=ua
            )
            login_user(user, remember=remember)

            if is_api:
                return api_success(user.to_dict(), message="Authentication successful.")

            flash(f"Welcome back, {user.first_name}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))
        except AppException as e:
            if is_api:
                return api_error(e.message, e.status_code)
            flash(e.message, "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    AuthService.logout(current_user, ip_address=ip_addr, user_agent=ua)
    logout_user()

    if request.is_json or request.path.startswith("/api/"):
        return api_success(message="Logged out successfully.")

    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        data = request.form
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        email = data.get("email", "").strip()

        try:
            AuthService.update_profile(current_user, first_name, last_name, email)
            flash("Profile updated successfully.", "success")
            return redirect(url_for("auth.profile"))
        except AppException as e:
            flash(e.message, "danger")

    return render_template("auth/profile.html", user=current_user)
