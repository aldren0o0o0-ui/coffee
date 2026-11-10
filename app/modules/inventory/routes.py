from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.core.decorators import roles_required, permission_required
from app.core.permissions import Roles, Permissions
from app.modules.inventory.services import InventoryService
from app.modules.inventory.models import (
    StockMovementType, StockMovement, Ingredient, Supplier, Purchase, PurchaseStatus
)
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException
from app.core.pagination import paginate_query

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/", methods=["GET"])
@login_required
@permission_required(Permissions.INVENTORY_VIEW)
def index():
    """Inventory Overview Dashboard (Section 29)."""
    stats = InventoryService.get_inventory_stats()
    low_stock_items = InventoryService.get_low_stock_items()[:10]
    recent_movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(8).all()
    all_items = Ingredient.query.filter_by(is_active=True).order_by(Ingredient.name.asc()).all()

    return render_template(
        "inventory/index.html",
        stats=stats,
        low_stock_items=low_stock_items,
        recent_movements=recent_movements,
        all_items=all_items,
        movement_types=StockMovementType.ALL
    )


@inventory_bp.route("/items", methods=["GET"])
@login_required
@permission_required(Permissions.INVENTORY_VIEW)
def items():
    """Paginated Raw Material Item Directory (Section 30)."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "")
    category_id = request.args.get("category_id", type=int)
    stock_status = request.args.get("status")  # 'OUT_OF_STOCK', 'LOW_STOCK', 'IN_STOCK'
    active_state = request.args.get("active", "1")

    pagination = InventoryService.get_items_paginated(
        page=page,
        per_page=15,
        category_id=category_id,
        search=search,
        stock_status=stock_status,
        active_only=(active_state == "1")
    )

    categories = InventoryService.get_inventory_categories()
    suppliers = InventoryService.get_suppliers()
    uoms = InventoryService.get_units_of_measure()

    return render_template(
        "inventory/items.html",
        pagination=pagination,
        search=search,
        selected_category_id=category_id,
        stock_status=stock_status,
        active_state=active_state,
        categories=categories,
        suppliers=suppliers,
        uoms=uoms
    )


@inventory_bp.route("/items/create", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.INVENTORY_CREATE)
def create_item():
    if request.method == "POST":
        data = request.form
        try:
            item = InventoryService.create_item(
                name=data.get("name"),
                sku=data.get("sku"),
                category_id=data.get("category_id"),
                unit_of_measure_id=data.get("unit_of_measure_id"),
                initial_quantity=data.get("current_stock", 0),
                minimum_stock=data.get("minimum_stock", 10),
                reorder_level=data.get("reorder_level", 10),
                cost_per_unit=data.get("cost_per_unit", 0),
                supplier_id=data.get("supplier_id"),
                description=data.get("description", ""),
                user_id=current_user.id
            )
            flash(f"Inventory item '{item.name}' added successfully.", "success")
            return redirect(url_for("inventory.items"))
        except AppException as e:
            flash(e.message, "danger")

    categories = InventoryService.get_inventory_categories()
    suppliers = InventoryService.get_suppliers()
    uoms = InventoryService.get_units_of_measure()
    return render_template("inventory/form.html", item=None, categories=categories, suppliers=suppliers, uoms=uoms)


@inventory_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.INVENTORY_UPDATE)
def edit_item(item_id):
    item = InventoryService.get_item_by_id(item_id)
    if request.method == "POST":
        data = request.form
        try:
            InventoryService.update_item(
                item_id=item.id,
                name=data.get("name"),
                category_id=data.get("category_id"),
                unit_of_measure_id=data.get("unit_of_measure_id"),
                minimum_stock=data.get("minimum_stock"),
                reorder_level=data.get("reorder_level"),
                cost_per_unit=data.get("cost_per_unit"),
                supplier_id=data.get("supplier_id"),
                description=data.get("description"),
                is_active="is_active" in data
            )
            flash(f"Inventory item '{item.name}' updated successfully.", "success")
            return redirect(url_for("inventory.items"))
        except AppException as e:
            flash(e.message, "danger")

    categories = InventoryService.get_inventory_categories()
    suppliers = InventoryService.get_suppliers()
    uoms = InventoryService.get_units_of_measure()
    return render_template("inventory/form.html", item=item, categories=categories, suppliers=suppliers, uoms=uoms)


@inventory_bp.route("/adjust", methods=["POST"])
@login_required
@permission_required(Permissions.INVENTORY_ADJUST)
def adjust_stock():
    """Atomic Stock Adjustment Action (Section 23, 24)."""
    data = request.form
    item_id = data.get("ingredient_id", type=int)
    quantity = data.get("quantity")
    reason = data.get("reason")
    notes = data.get("notes", "")

    try:
        movement = InventoryService.adjust_stock(
            item_id=item_id,
            quantity=quantity,
            reason=reason,
            notes=notes,
            user_id=current_user.id
        )
        flash(f"Stock adjusted successfully for {movement.ingredient.name} ({movement.quantity:+f} {movement.unit}).", "success")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(request.referrer or url_for("inventory.items"))


# Backwards compatibility route
@inventory_bp.route("/<int:ingredient_id>/movement", methods=["POST"])
@login_required
@permission_required(Permissions.INVENTORY_ADJUST)
def record_legacy_movement(ingredient_id):
    data = request.form
    try:
        InventoryService.record_movement(
            ingredient_id=ingredient_id,
            movement_type=data.get("movement_type"),
            quantity=data.get("quantity"),
            reference=data.get("reference", ""),
            notes=data.get("notes", ""),
            reason=data.get("reason", "Logged via movement form"),
            user_id=current_user.id
        )
        flash("Stock movement logged successfully.", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(request.referrer or url_for("inventory.index"))


@inventory_bp.route("/movements", methods=["GET"])
@login_required
@permission_required(Permissions.INVENTORY_VIEW_MOVEMENTS)
def movements():
    """Stock Movement Ledger History (Section 31)."""
    page = request.args.get("page", 1, type=int)
    item_id = request.args.get("item_id", type=int)
    movement_type = request.args.get("movement_type")

    query = StockMovement.query
    if item_id:
        query = query.filter_by(ingredient_id=item_id)
    if movement_type:
        query = query.filter_by(movement_type=movement_type)

    query = query.order_by(StockMovement.created_at.desc())
    pagination = paginate_query(query, page=page, per_page=20)
    all_items = Ingredient.query.order_by(Ingredient.name.asc()).all()

    return render_template(
        "inventory/movements.html",
        pagination=pagination,
        selected_item_id=item_id,
        selected_type=movement_type,
        movement_types=StockMovementType.ALL,
        all_items=all_items
    )


@inventory_bp.route("/purchases", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.INVENTORY_RECEIVE)
def purchases():
    """Purchase Order & Receiving Management (Section 25, 26, 27)."""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status")

    if request.method == "POST":
        data = request.form
        try:
            # Parse line items
            items_data = []
            item_ids = data.getlist("item_id[]")
            quantities = data.getlist("quantity[]")
            unit_costs = data.getlist("unit_cost[]")

            for i in range(len(item_ids)):
                if item_ids[i] and quantities[i]:
                    items_data.append({
                        "ingredient_id": int(item_ids[i]),
                        "quantity": quantities[i],
                        "unit_cost": unit_costs[i] if i < len(unit_costs) else "0.00"
                    })

            purchase = InventoryService.create_purchase(
                supplier_id=int(data.get("supplier_id")),
                reference_number=data.get("reference_number"),
                items_data=items_data,
                notes=data.get("notes", ""),
                user_id=current_user.id
            )
            flash(f"Purchase order '{purchase.reference_number}' created as DRAFT.", "success")
            return redirect(url_for("inventory.purchases"))
        except AppException as e:
            flash(e.message, "danger")

    pagination = InventoryService.get_purchases_paginated(page=page, per_page=15, status=status)
    suppliers = InventoryService.get_suppliers()
    all_items = Ingredient.query.filter_by(is_active=True).order_by(Ingredient.name.asc()).all()

    return render_template(
        "inventory/purchases.html",
        pagination=pagination,
        suppliers=suppliers,
        all_items=all_items,
        selected_status=status
    )


@inventory_bp.route("/purchases/<int:purchase_id>/receive", methods=["POST"])
@login_required
@permission_required(Permissions.INVENTORY_RECEIVE)
def receive_purchase(purchase_id):
    """Atomically receive a purchase order into stock."""
    try:
        purchase = InventoryService.receive_purchase(purchase_id, user_id=current_user.id)
        flash(f"Purchase '{purchase.reference_number}' received! Inventory stock updated.", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("inventory.purchases"))


@inventory_bp.route("/purchases/<int:purchase_id>/cancel", methods=["POST"])
@login_required
@permission_required(Permissions.INVENTORY_RECEIVE)
def cancel_purchase(purchase_id):
    """Cancel purchase order."""
    try:
        purchase = InventoryService.cancel_purchase(purchase_id, user_id=current_user.id)
        flash(f"Purchase '{purchase.reference_number}' has been cancelled.", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("inventory.purchases"))


@inventory_bp.route("/suppliers", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.INVENTORY_MANAGE_SUPPLIERS)
def suppliers():
    """Supplier Directory Management (Section 20)."""
    if request.method == "POST":
        data = request.form
        try:
            supplier = InventoryService.create_supplier(
                name=data.get("name"),
                contact_person=data.get("contact_person"),
                email=data.get("email"),
                phone=data.get("phone"),
                address=data.get("address"),
                notes=data.get("notes")
            )
            flash(f"Supplier '{supplier.name}' registered successfully.", "success")
            return redirect(url_for("inventory.suppliers"))
        except AppException as e:
            flash(e.message, "danger")

    suppliers_list = InventoryService.get_suppliers()
    return render_template("inventory/suppliers.html", suppliers=suppliers_list)


@inventory_bp.route("/suppliers/<int:supplier_id>/edit", methods=["POST"])
@login_required
@permission_required(Permissions.INVENTORY_MANAGE_SUPPLIERS)
def edit_supplier(supplier_id):
    data = request.form
    try:
        supplier = InventoryService.update_supplier(
            supplier_id=supplier_id,
            name=data.get("name"),
            contact_person=data.get("contact_person"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            notes=data.get("notes")
        )
        flash(f"Supplier '{supplier.name}' updated successfully.", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(url_for("inventory.suppliers"))


# API endpoints
@inventory_bp.route("/api/items", methods=["GET"])
@login_required
def api_items():
    items = InventoryService.get_items_paginated(page=1, per_page=200, active_only=True).items
    return api_success([i.to_dict() for i in items])
