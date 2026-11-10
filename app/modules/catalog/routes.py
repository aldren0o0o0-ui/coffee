import json
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.core.decorators import roles_required, permission_required
from app.core.permissions import Roles, Permissions
from app.modules.catalog.services import CatalogService
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/", methods=["GET"])
@login_required
@permission_required(Permissions.CATALOG_VIEW)
def index():
    page = request.args.get("page", 1, type=int)
    category_id = request.args.get("category_id", type=int)
    search = request.args.get("q", "")
    availability = request.args.get("available")  # '1', '0', or None
    active_state = request.args.get("active", "1")  # default to active products

    available_only = True if availability == "1" else False
    active_only = True if active_state == "1" else False

    pagination = CatalogService.get_products_paginated(
        page=page,
        per_page=12,
        category_id=category_id,
        search=search,
        available_only=available_only,
        active_only=active_only
    )
    categories = CatalogService.get_categories()
    stats = CatalogService.get_catalog_stats()

    return render_template(
        "catalog/index.html",
        pagination=pagination,
        categories=categories,
        selected_category_id=category_id,
        search=search,
        availability=availability,
        active_state=active_state,
        stats=stats
    )


@catalog_bp.route("/products/create", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.CATALOG_CREATE)
def create_product():
    if request.method == "POST":
        data = request.form
        try:
            # Parse dynamic variant inputs if present
            variants_data = []
            variant_names = data.getlist("variant_name[]")
            variant_skus = data.getlist("variant_sku[]")
            variant_prices = data.getlist("variant_price[]")
            variant_costs = data.getlist("variant_cost[]")

            for i in range(len(variant_names)):
                v_name = variant_names[i].strip()
                if v_name:
                    variants_data.append({
                        "name": v_name,
                        "sku": variant_skus[i].strip() if i < len(variant_skus) else "",
                        "price": variant_prices[i] if i < len(variant_prices) else data.get("base_price"),
                        "cost_price": variant_costs[i] if i < len(variant_costs) else "0.00"
                    })

            product = CatalogService.create_product(
                name=data.get("name"),
                category_id=int(data.get("category_id")),
                base_price=data.get("base_price"),
                cost_price=data.get("cost_price", 0.0) or 0.0,
                sku=data.get("sku"),
                description=data.get("description", ""),
                image_url=data.get("image_url", ""),
                is_available="is_available" in data,
                is_active="is_active" in data,
                display_order=data.get("display_order", 0),
                variants_data=variants_data
            )
            flash(f"Product '{product.name}' created successfully.", "success")
            return redirect(url_for("catalog.index"))
        except AppException as e:
            flash(e.message, "danger")

    categories = CatalogService.get_categories(active_only=True)
    return render_template("catalog/product_form.html", product=None, categories=categories)


@catalog_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.CATALOG_UPDATE)
def edit_product(product_id):
    product = CatalogService.get_product_by_id(product_id)
    if request.method == "POST":
        data = request.form
        try:
            CatalogService.update_product(
                product_id=product.id,
                name=data.get("name"),
                category_id=int(data.get("category_id")),
                base_price=data.get("base_price"),
                cost_price=data.get("cost_price", 0.0) or 0.0,
                sku=data.get("sku"),
                description=data.get("description", ""),
                image_url=data.get("image_url", ""),
                is_available="is_available" in data,
                is_active="is_active" in data,
                display_order=data.get("display_order", 0)
            )
            flash(f"Product '{product.name}' updated successfully.", "success")
            return redirect(url_for("catalog.index"))
        except AppException as e:
            flash(e.message, "danger")

    categories = CatalogService.get_categories()
    return render_template("catalog/product_form.html", product=product, categories=categories)


@catalog_bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_UPDATE)
def toggle_product(product_id):
    product = CatalogService.toggle_availability(product_id)
    state = "available" if product.is_available else "unavailable"
    flash(f"Product '{product.name}' is now marked as {state}.", "info")
    return redirect(request.referrer or url_for("catalog.index"))


@catalog_bp.route("/products/<int:product_id>/toggle-active", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_DEACTIVATE)
def toggle_active_product(product_id):
    product = CatalogService.toggle_active(product_id)
    state = "active" if product.is_active else "archived / inactive"
    flash(f"Product '{product.name}' is now {state}.", "info")
    return redirect(request.referrer or url_for("catalog.index"))


@catalog_bp.route("/products/<int:product_id>/variants/create", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_UPDATE)
def add_variant(product_id):
    data = request.form
    try:
        variant = CatalogService.create_variant(
            product_id=product_id,
            name=data.get("name"),
            price=data.get("price"),
            cost_price=data.get("cost_price", 0.0),
            sku=data.get("sku"),
            is_available="is_available" in data
        )
        flash(f"Variant '{variant.name}' added successfully.", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("catalog.edit_product", product_id=product_id))


@catalog_bp.route("/variants/<int:variant_id>/delete", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_UPDATE)
def delete_variant(variant_id):
    product_id = request.form.get("product_id", type=int)
    try:
        CatalogService.delete_variant(variant_id)
        flash("Product variant removed.", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("catalog.edit_product", product_id=product_id) if product_id else url_for("catalog.index"))


@catalog_bp.route("/categories", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.CATALOG_MANAGE)
def categories():
    if request.method == "POST":
        data = request.form
        try:
            cat = CatalogService.create_category(
                name=data.get("name"),
                description=data.get("description", ""),
                display_order=data.get("display_order", 0),
                slug=data.get("slug")
            )
            flash(f"Category '{cat.name}' added successfully.", "success")
            return redirect(url_for("catalog.categories"))
        except AppException as e:
            flash(e.message, "danger")

    cats = CatalogService.get_categories()
    return render_template("catalog/categories.html", categories=cats)


@catalog_bp.route("/categories/<int:category_id>/edit", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_MANAGE)
def edit_category(category_id):
    data = request.form
    try:
        cat = CatalogService.update_category(
            category_id=category_id,
            name=data.get("name"),
            description=data.get("description"),
            display_order=data.get("display_order"),
            is_active="is_active" in data,
            slug=data.get("slug")
        )
        flash(f"Category '{cat.name}' updated successfully.", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("catalog.categories"))


@catalog_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@permission_required(Permissions.CATALOG_MANAGE)
def delete_category(category_id):
    try:
        CatalogService.delete_category(category_id)
        flash("Category removed successfully.", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("catalog.categories"))


# API endpoints for POS & JSON integrations
@catalog_bp.route("/api/products", methods=["GET"])
@login_required
def api_products():
    category_id = request.args.get("category_id", type=int)
    products = CatalogService.get_products_paginated(
        page=1, per_page=100, category_id=category_id, available_only=True, active_only=True
    ).items
    return api_success([p.to_dict() for p in products])


@catalog_bp.route("/api/categories", methods=["GET"])
@login_required
def api_categories():
    categories = CatalogService.get_categories(active_only=True)
    return api_success([c.to_dict() for c in categories])
