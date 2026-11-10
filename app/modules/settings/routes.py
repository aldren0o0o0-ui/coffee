from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required
from app.core.decorators import roles_required
from app.core.permissions import Roles
from app.modules.settings.services import SettingsService

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER)
def index():
    if request.method == "POST":
        data = request.form
        for key in ["store_name", "currency_symbol", "tax_rate", "receipt_header", "receipt_footer"]:
            if key in data:
                SettingsService.set_setting(key, data[key])
        flash("Store settings updated successfully.", "success")
        return redirect(url_for("settings.index"))

    settings = SettingsService.get_all_settings()
    return render_template("settings/index.html", settings=settings)
