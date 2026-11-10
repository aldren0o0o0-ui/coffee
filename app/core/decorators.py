from functools import wraps
from flask import request, abort, redirect, url_for
from flask_login import current_user
from app.core.permissions import role_has_permission
from app.core.responses import api_error


def roles_required(*roles):
    """Ensure current user is authenticated and possesses one of the authorized roles."""
    normalized_roles = [r.upper() for r in roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api/"):
                    return api_error("Authentication required.", 401)
                return redirect(url_for("auth.login", next=request.url))

            if not current_user.is_active:
                if request.is_json or request.path.startswith("/api/"):
                    return api_error("Account is inactive.", 403)
                abort(403)

            if current_user.role.upper() not in normalized_roles:
                if request.is_json or request.path.startswith("/api/"):
                    return api_error("Access forbidden for your role.", 403)
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """Ensure current user has the specific capability permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api/"):
                    return api_error("Authentication required.", 401)
                return redirect(url_for("auth.login", next=request.url))

            if not current_user.is_active:
                if request.is_json or request.path.startswith("/api/"):
                    return api_error("Account is inactive.", 403)
                abort(403)

            if not role_has_permission(current_user.role, permission):
                if request.is_json or request.path.startswith("/api/"):
                    return api_error(f"Missing required permission: {permission}", 403)
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator
