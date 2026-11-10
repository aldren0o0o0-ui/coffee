from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.core.decorators import permission_required
from app.core.permissions import Permissions
from app.modules.recipes.services import RecipeService
from app.modules.catalog.services import CatalogService
from app.modules.inventory.services import InventoryService
from app.core.responses import api_success, api_error
from app.core.exceptions import AppException

recipes_bp = Blueprint("recipes", __name__)


@recipes_bp.route("/", methods=["GET"])
@login_required
@permission_required(Permissions.RECIPES_VIEW)
def index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "")
    active_only = request.args.get("active", "") == "1"

    recipes_pagination = RecipeService.get_all_recipes(
        page=page,
        per_page=30,
        search=search,
        active_only=active_only
    )

    # Also list catalog products that do NOT have a recipe configured yet
    all_products = CatalogService.get_products_paginated(page=1, per_page=100, active_only=True).items
    unconfigured_products = [p for p in all_products if not RecipeService.get_recipe(product_id=p.id)]

    return render_template(
        "recipes/index.html",
        recipes_pagination=recipes_pagination,
        unconfigured_products=unconfigured_products,
        search=search,
        active_only=active_only
    )


@recipes_bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.RECIPES_CREATE)
def create():
    product_id = request.args.get("product_id", type=int)
    variant_id = request.args.get("variant_id", type=int)

    if request.method == "POST":
        p_id = request.form.get("product_id", type=int)
        v_id = request.form.get("variant_id", type=int)
        name = request.form.get("name", "")
        description = request.form.get("description", "")
        instructions = request.form.get("instructions", "")
        prep_notes = request.form.get("prep_notes", "")
        yield_quantity = request.form.get("yield_quantity", 1.0)
        yield_unit = request.form.get("yield_unit", "serving")

        ingredient_ids = request.form.getlist("ingredient_id[]")
        quantities = request.form.getlist("quantity_required[]")
        units = request.form.getlist("unit[]")
        notes = request.form.getlist("item_notes[]")

        items_data = []
        for idx in range(len(ingredient_ids)):
            ing_id = ingredient_ids[idx]
            qty = quantities[idx] if idx < len(quantities) else None
            unit_str = units[idx] if idx < len(units) else None
            item_note = notes[idx] if idx < len(notes) else None

            if ing_id and qty:
                items_data.append({
                    "ingredient_id": ing_id,
                    "quantity_required": qty,
                    "unit": unit_str,
                    "notes": item_note
                })

        try:
            recipe = RecipeService.save_recipe(
                product_id=p_id,
                variant_id=v_id,
                items_data=items_data,
                instructions=instructions,
                name=name,
                description=description,
                prep_notes=prep_notes,
                yield_quantity=yield_quantity,
                yield_unit=yield_unit,
                user_id=current_user.id
            )
            flash(f"Recipe '{recipe.target_name}' created successfully!", "success")
            return redirect(url_for("recipes.edit", recipe_id=recipe.id))
        except AppException as e:
            flash(e.message, "danger")

    products = CatalogService.get_products_paginated(page=1, per_page=200, active_only=True).items
    all_ingredients = InventoryService.get_items_paginated(page=1, per_page=200, active_only=True).items
    uoms = InventoryService.get_units_of_measure()

    return render_template(
        "recipes/form.html",
        is_edit=False,
        recipe=None,
        selected_product_id=product_id,
        selected_variant_id=variant_id,
        products=products,
        all_ingredients=all_ingredients,
        uoms=uoms
    )


@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(Permissions.RECIPES_EDIT)
def edit(recipe_id):
    recipe = RecipeService.get_recipe_by_id(recipe_id)

    if request.method == "POST":
        name = request.form.get("name", "")
        description = request.form.get("description", "")
        instructions = request.form.get("instructions", "")
        prep_notes = request.form.get("prep_notes", "")
        yield_quantity = request.form.get("yield_quantity", 1.0)
        yield_unit = request.form.get("yield_unit", "serving")

        ingredient_ids = request.form.getlist("ingredient_id[]")
        quantities = request.form.getlist("quantity_required[]")
        units = request.form.getlist("unit[]")
        notes = request.form.getlist("item_notes[]")

        items_data = []
        for idx in range(len(ingredient_ids)):
            ing_id = ingredient_ids[idx]
            qty = quantities[idx] if idx < len(quantities) else None
            unit_str = units[idx] if idx < len(units) else None
            item_note = notes[idx] if idx < len(notes) else None

            if ing_id and qty:
                items_data.append({
                    "ingredient_id": ing_id,
                    "quantity_required": qty,
                    "unit": unit_str,
                    "notes": item_note
                })

        try:
            recipe = RecipeService.save_recipe(
                product_id=recipe.product_id,
                variant_id=recipe.product_variant_id,
                items_data=items_data,
                instructions=instructions,
                name=name,
                description=description,
                prep_notes=prep_notes,
                yield_quantity=yield_quantity,
                yield_unit=yield_unit,
                user_id=current_user.id
            )
            flash(f"Recipe '{recipe.target_name}' updated successfully!", "success")
            return redirect(url_for("recipes.edit", recipe_id=recipe.id))
        except AppException as e:
            flash(e.message, "danger")

    products = CatalogService.get_products_paginated(page=1, per_page=200, active_only=True).items
    all_ingredients = InventoryService.get_items_paginated(page=1, per_page=200, active_only=True).items
    uoms = InventoryService.get_units_of_measure()

    return render_template(
        "recipes/form.html",
        is_edit=True,
        recipe=recipe,
        selected_product_id=recipe.product_id,
        selected_variant_id=recipe.product_variant_id,
        products=products,
        all_ingredients=all_ingredients,
        uoms=uoms
    )


@recipes_bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
@permission_required(Permissions.RECIPES_DELETE)
def delete(recipe_id):
    RecipeService.delete_recipe(recipe_id, user_id=current_user.id)
    flash("Recipe deleted successfully.", "info")
    return redirect(url_for("recipes.index"))


@recipes_bp.route("/<int:recipe_id>/toggle", methods=["POST"])
@login_required
@permission_required(Permissions.RECIPES_EDIT)
def toggle(recipe_id):
    recipe = RecipeService.toggle_recipe_active(recipe_id, user_id=current_user.id)
    status_str = "activated" if recipe.is_active else "deactivated"
    flash(f"Recipe '{recipe.target_name}' {status_str}.", "info")
    return redirect(request.referrer or url_for("recipes.index"))


# Backward compatibility route for /recipes/<product_id>
@recipes_bp.route("/<int:product_id>", methods=["GET", "POST"])
@login_required
def legacy_product_recipe(product_id):
    recipe = RecipeService.get_recipe(product_id=product_id)
    if recipe:
        return redirect(url_for("recipes.edit", recipe_id=recipe.id))
    return redirect(url_for("recipes.create", product_id=product_id))


# --- JSON API Endpoints for POS & Dynamic UI ---

@recipes_bp.route("/api/<int:product_id>", methods=["GET"])
@login_required
def api_recipe(product_id):
    variant_id = request.args.get("variant_id", type=int)
    recipe = RecipeService.get_recipe(product_id=product_id, variant_id=variant_id)
    if not recipe:
        return api_error("No active recipe formulation configured for this item.", 404)
    return api_success(recipe.to_dict())


@recipes_bp.route("/api/availability", methods=["GET"])
@login_required
def api_availability():
    product_id = request.args.get("product_id", type=int)
    variant_id = request.args.get("variant_id", type=int)
    qty = request.args.get("quantity", 1, type=int)

    if not product_id and not variant_id:
        return api_error("Missing product_id or variant_id.", 400)

    is_avail, missing = RecipeService.check_stock_availability(
        product_id=product_id,
        variant_id=variant_id,
        order_quantity=qty
    )
    return api_success({
        "is_available": is_avail,
        "missing_ingredients": missing
    })
