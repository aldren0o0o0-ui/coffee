from flask import jsonify, render_template, request, flash, redirect, url_for


def api_success(data=None, message="Success", status_code=200, **kwargs):
    """Standardized JSON success response."""
    response = {
        "status": "success",
        "message": message,
        "data": data if data is not None else {}
    }
    response.update(kwargs)
    return jsonify(response), status_code


def api_error(message="An error occurred", status_code=400, errors=None, **kwargs):
    """Standardized JSON error response."""
    response = {
        "status": "error",
        "message": message,
        "errors": errors if errors is not None else []
    }
    response.update(kwargs)
    return jsonify(response), status_code


def render_or_json(template_name, context=None, status_code=200):
    """Helper to render HTML or return JSON depending on Accept header or request type."""
    context = context or {}
    if request.is_json or request.headers.get("Accept") == "application/json":
        return api_success(data=context, status_code=status_code)
    return render_template(template_name, **context), status_code
