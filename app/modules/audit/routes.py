from flask import Blueprint, request, render_template
from flask_login import login_required
from app.core.decorators import roles_required
from app.core.permissions import Roles
from app.modules.audit.services import AuditService

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def index():
    page = request.args.get("page", 1, type=int)
    action = request.args.get("action", "")
    entity_type = request.args.get("entity_type", "")

    pagination = AuditService.get_logs_paginated(
        page=page, per_page=20, action=action if action else None, entity_type=entity_type if entity_type else None
    )

    return render_template(
        "audit/index.html",
        pagination=pagination,
        selected_action=action,
        selected_entity=entity_type
    )
