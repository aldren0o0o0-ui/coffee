import os
from flask import Flask, render_template, request, jsonify
from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter
from app.core.exceptions import AppException
from app.core.responses import api_error
from app.core.utilities import format_datetime, format_currency


def create_app(config_name=None):
    """Application factory for Coffee Shop SME Management System."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Register active blueprints for Phase 1 - 4
    from app.modules.dashboard import dashboard_bp
    from app.modules.auth import auth_bp
    from app.modules.users import users_bp
    from app.modules.catalog import catalog_bp
    from app.modules.inventory import inventory_bp
    from app.modules.recipes import recipes_bp
    from app.modules.pos import pos_bp
    from app.modules.sales import sales_bp
    from app.modules.reports import reports_bp
    from app.modules.expenses import expenses_bp
    from app.modules.employees import employees_bp
    from app.modules.settings import settings_bp
    from app.modules.audit import audit_bp

    app.register_blueprint(dashboard_bp, url_prefix="")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(catalog_bp, url_prefix="/catalog")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(recipes_bp, url_prefix="/recipes")
    app.register_blueprint(pos_bp, url_prefix="/pos")
    app.register_blueprint(sales_bp, url_prefix="/sales")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(expenses_bp, url_prefix="/expenses")
    app.register_blueprint(employees_bp, url_prefix="/staff")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(audit_bp, url_prefix="/audit")

    @app.route("/employees")
    @app.route("/employees/<path:subpath>")
    def employees_redirect(subpath=""):
        from flask import redirect
        return redirect(f"/staff/{subpath}" if subpath else "/staff")

    @app.route("/health")
    def health_check():
        return jsonify({"status": "healthy", "service": "Coffee Shop SME"}), 200

    # Template context processors
    @app.context_processor
    def inject_globals():
        from app.modules.settings.services import SettingsService
        try:
            curr_symbol = SettingsService.get_setting("currency_symbol", "₱")
        except Exception:
            curr_symbol = "₱"

        def _format_currency(amount, symbol=None):
            return format_currency(amount, symbol=symbol or curr_symbol)

        return {
            "format_datetime": format_datetime,
            "format_currency": _format_currency,
            "currency_symbol": curr_symbol,
            "store_name": app.config.get("STORE_NAME", "John Coffee"),
            "app_name": app.config.get("APP_NAME", "Coffee Shop SME"),
        }

    # Centralized HTTP Error Handlers
    @app.errorhandler(AppException)
    def handle_app_exception(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error(e.message, e.status_code, payload=e.payload)
        return render_template("errors/error.html", error_code=e.status_code, message=e.message), e.status_code

    @app.errorhandler(400)
    def bad_request(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Bad request payload.", 400)
        return render_template("errors/error.html", error_code=400, message="The request could not be processed due to invalid parameters."), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Authentication required.", 401)
        return render_template("errors/error.html", error_code=401, message="You must be signed in to access this resource."), 401

    @app.errorhandler(403)
    def forbidden(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Access forbidden.", 403)
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Resource not found.", 404)
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("HTTP method not allowed.", 405)
        return render_template("errors/error.html", error_code=405, message="The requested method is not allowed for this endpoint."), 405

    @app.errorhandler(409)
    def conflict(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Resource conflict.", 409)
        return render_template("errors/error.html", error_code=409, message="A data conflict occurred."), 409

    @app.errorhandler(422)
    def unprocessable_entity(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Unprocessable entity.", 422)
        return render_template("errors/error.html", error_code=422, message="Validation failed on submitted entity."), 422

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Too many requests. Please slow down.", 429)
        return render_template("errors/error.html", error_code=429, message="Rate limit exceeded. Please wait a moment before trying again."), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Internal server error.", 500)
        return render_template("errors/500.html"), 500

    return app
