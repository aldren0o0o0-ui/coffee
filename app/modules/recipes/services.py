from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db
from app.modules.recipes.models import Recipe, RecipeItem
from app.modules.recipes.validators import validate_recipe_data, validate_recipe_items
from app.modules.recipes.units import convert_quantity
from app.modules.catalog.models import Product, ProductVariant
from app.modules.inventory.models import Ingredient, StockMovement, StockMovementType
from app.modules.auth.models import AuditLog
from app.core.exceptions import NotFoundError, ValidationError, InsufficientStockError


class RecipeService:
    @staticmethod
    def get_recipe(product_id=None, variant_id=None):
        """
        Retrieve the active recipe for a product or variant.
        Variant-specific recipes take precedence over base product recipes.
        """
        if variant_id:
            recipe = Recipe.query.filter_by(product_variant_id=variant_id, is_active=True).first()
            if recipe:
                return recipe

        if product_id:
            return Recipe.query.filter_by(product_id=product_id, product_variant_id=None, is_active=True).first()

        return None

    # Backward compatibility alias
    @staticmethod
    def get_recipe_by_product(product_id):
        return RecipeService.get_recipe(product_id=product_id)

    @staticmethod
    def get_recipe_by_id(recipe_id):
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            raise NotFoundError(f"Recipe with ID {recipe_id} not found.")
        return recipe

    @staticmethod
    def get_all_recipes(page=1, per_page=50, search="", active_only=False):
        """Retrieve paginated recipes with filtering."""
        query = Recipe.query
        if active_only:
            query = query.filter(Recipe.is_active.is_(True))

        if search:
            s = f"%{search.strip()}%"
            query = query.outerjoin(Product, Recipe.product_id == Product.id).outerjoin(
                ProductVariant, Recipe.product_variant_id == ProductVariant.id
            ).filter(
                db.or_(
                    Recipe.name.ilike(s),
                    Product.name.ilike(s),
                    ProductVariant.name.ilike(s)
                )
            )

        return query.order_by(Recipe.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def save_recipe(product_id=None, variant_id=None, items_data=None, instructions="",
                    name=None, description=None, prep_notes=None, yield_quantity=1.0,
                    yield_unit="serving", user_id=None):
        """
        Create or update a recipe formulation atomically.
        """
        validate_recipe_data(
            product_id=product_id,
            product_variant_id=variant_id,
            items_data=items_data,
            yield_quantity=yield_quantity
        )

        product = db.session.get(Product, product_id) if product_id else None
        variant = db.session.get(ProductVariant, variant_id) if variant_id else None

        if variant and not product:
            product = variant.product
            product_id = product.id if product else None

        # Check for existing recipe matching this target
        if variant_id:
            recipe = Recipe.query.filter_by(product_variant_id=variant_id).first()
        else:
            recipe = Recipe.query.filter_by(product_id=product_id, product_variant_id=None).first()

        is_new = recipe is None
        if is_new:
            recipe = Recipe(
                product_id=product_id,
                product_variant_id=variant_id,
                name=name.strip() if name else (variant.name if variant else (product.name if product else "New Recipe")),
                description=description.strip() if description else "",
                instructions=instructions.strip() if instructions else "",
                prep_notes=prep_notes.strip() if prep_notes else "",
                yield_quantity=Decimal(str(yield_quantity or 1.0)),
                yield_unit=yield_unit.strip() if yield_unit else "serving",
                is_active=True
            )
            db.session.add(recipe)
        else:
            if name is not None:
                recipe.name = name.strip()
            if description is not None:
                recipe.description = description.strip()
            recipe.instructions = instructions.strip() if instructions else ""
            if prep_notes is not None:
                recipe.prep_notes = prep_notes.strip()
            recipe.yield_quantity = Decimal(str(yield_quantity or 1.0))
            recipe.yield_unit = yield_unit.strip() if yield_unit else "serving"
            recipe.updated_at = datetime.utcnow()
            recipe.version += 1
            # Clear previous formulation items
            RecipeItem.query.filter_by(recipe_id=recipe.id).delete()

        db.session.flush()

        # Add formulation items
        for order_idx, item in enumerate(items_data, 1):
            ing_id = int(item["ingredient_id"])
            qty = Decimal(str(item["quantity_required"]))
            ingredient = db.session.get(Ingredient, ing_id)
            unit_str = item.get("unit") or (ingredient.unit if ingredient else "g")
            uom_id = item.get("unit_of_measure_id") or (ingredient.unit_of_measure_id if ingredient else None)

            ri = RecipeItem(
                recipe_id=recipe.id,
                ingredient_id=ing_id,
                quantity_required=qty,
                unit=unit_str,
                unit_of_measure_id=uom_id,
                notes=item.get("notes", "").strip() if item.get("notes") else None,
                display_order=order_idx
            )
            db.session.add(ri)

        db.session.flush()

        # Update product or variant cost_price to match calculated recipe cost
        computed_cogs = recipe.total_cost_decimal
        if variant:
            variant.cost_price = computed_cogs
        elif product:
            product.cost_price = computed_cogs

        # Audit Log
        AuditLog.log(
            action="RECIPE_CREATED" if is_new else "RECIPE_UPDATED",
            user_id=user_id,
            details=f"Saved recipe '{recipe.target_name}' (ID: {recipe.id}, COGS: ${computed_cogs:.2f}, Items: {len(items_data)})"
        )

        db.session.commit()
        return recipe

    @staticmethod
    def delete_recipe(recipe_id, user_id=None):
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return False

        target_name = recipe.target_name
        db.session.delete(recipe)

        AuditLog.log(
            action="RECIPE_DELETED",
            user_id=user_id,
            details=f"Deleted recipe for '{target_name}' (ID: {recipe_id})"
        )

        db.session.commit()
        return True

    @staticmethod
    def toggle_recipe_active(recipe_id, user_id=None):
        recipe = RecipeService.get_recipe_by_id(recipe_id)
        recipe.is_active = not recipe.is_active
        recipe.updated_at = datetime.utcnow()

        AuditLog.log(
            action="RECIPE_ACTIVATED" if recipe.is_active else "RECIPE_DEACTIVATED",
            user_id=user_id,
            details=f"Recipe '{recipe.target_name}' is_active set to {recipe.is_active}"
        )

        db.session.commit()
        return recipe

    @staticmethod
    def check_stock_availability(product_id, variant_id=None, order_quantity=1):
        """
        Check if there is sufficient stock of all recipe ingredients to make the ordered quantity.
        Returns: (is_available: bool, missing: list)
        """
        recipe = RecipeService.get_recipe(product_id=product_id, variant_id=variant_id)
        if not recipe or not recipe.items:
            # Non-recipe products are assumed available unless overridden
            return True, []

        order_qty_dec = Decimal(str(order_quantity))
        missing = []

        for item in recipe.items:
            if not item.ingredient:
                continue

            ing = item.ingredient
            # Convert recipe required quantity into the ingredient's storage unit
            try:
                converted_qty_per_serving = convert_quantity(item.quantity_required, item.unit, ing.unit)
            except Exception:
                converted_qty_per_serving = Decimal(str(item.quantity_required))

            total_needed = converted_qty_per_serving * order_qty_dec
            current_avail = Decimal(str(ing.current_quantity or 0))

            if current_avail < total_needed:
                missing.append({
                    "ingredient": ing.name,
                    "available": float(current_avail),
                    "needed": float(total_needed),
                    "unit": ing.unit
                })

        return len(missing) == 0, missing

    @staticmethod
    def get_operational_availability(product_id, variant_id=None):
        """
        Determine operational availability combining catalog flag with live recipe stock check.
        """
        if variant_id:
            variant = db.session.get(ProductVariant, variant_id)
            if not variant or not variant.is_available or not variant.is_active:
                return False
        elif product_id:
            product = db.session.get(Product, product_id)
            if not product or not product.is_available or not product.is_active:
                return False

        avail, _ = RecipeService.check_stock_availability(product_id, variant_id=variant_id, order_quantity=1)
        return avail

    @staticmethod
    def consume_recipe_ingredients(items_requirements, reference="Order", reference_type="SALE",
                                   reference_id=None, user_id=None):
        """
        CRITICAL ATOMIC INVENTORY DEDUCTION CONTRACT:
        1. Lock all required ingredient rows with pessimistic row-locking (with_for_update()).
        2. Verify complete aggregate stock availability.
        3. If ANY ingredient is insufficient, raise InsufficientStockError and abort.
        4. If ALL ingredients are available, deduct stock and record StockMovement entries.
        5. Invariant: EITHER ALL INGREDIENTS ARE DEDUCTED, OR NONE ARE DEDUCTED.
        """
        if not items_requirements:
            return []

        # Aggregate total required quantities by ingredient_id in the ingredient's storage unit
        totals_by_ingredient = {}
        notes_by_ingredient = {}

        for req in items_requirements:
            ing_id = int(req["ingredient_id"])
            qty_needed = Decimal(str(req["quantity"]))
            from_unit = req.get("unit")

            if ing_id not in totals_by_ingredient:
                totals_by_ingredient[ing_id] = Decimal("0.0000")
                notes_by_ingredient[ing_id] = []

            totals_by_ingredient[ing_id] += qty_needed
            if req.get("notes"):
                notes_by_ingredient[ing_id].append(req["notes"])

        ingredient_ids = list(totals_by_ingredient.keys())

        # Pessimistic Row-Level Locking on PostgreSQL
        locked_ingredients = db.session.query(Ingredient).filter(
            Ingredient.id.in_(ingredient_ids)
        ).with_for_update().all()

        locked_by_id = {ing.id: ing for ing in locked_ingredients}

        # Check availability for every required ingredient
        insufficient_errors = []
        for ing_id, total_needed in totals_by_ingredient.items():
            ing = locked_by_id.get(ing_id)
            if not ing:
                raise NotFoundError(f"Ingredient with ID {ing_id} not found in inventory.")

            current_qty = Decimal(str(ing.current_quantity or 0))
            if current_qty < total_needed:
                insufficient_errors.append(
                    f"{ing.name} (need {total_needed} {ing.unit}, available {current_qty} {ing.unit})"
                )

        if insufficient_errors:
            # ATOMIC ABORT: consume nothing, raise exception, caller rolls back
            err_msg = "Insufficient raw materials: " + ", ".join(insufficient_errors)
            raise InsufficientStockError(err_msg)

        # All ingredients are verified available: perform atomic stock deduction
        created_movements = []
        for ing_id, total_needed in totals_by_ingredient.items():
            ing = locked_by_id[ing_id]
            ing.current_quantity -= total_needed
            ing.updated_at = datetime.utcnow()

            combined_notes = "; ".join(notes_by_ingredient.get(ing_id, [])) or None

            movement = StockMovement(
                ingredient_id=ing.id,
                movement_type=StockMovementType.CONSUMPTION,
                quantity=-total_needed,
                unit_cost=ing.cost_per_unit,
                reference_type=reference_type,
                reference_id=reference_id,
                reference=reference,
                reason=f"POS recipe consumption for {reference}",
                notes=combined_notes,
                created_by_id=user_id
            )
            db.session.add(movement)
            created_movements.append(movement)

        db.session.flush()
        return created_movements

    # Backward compatibility helper
    @staticmethod
    def deduct_inventory_for_sale_item(product_id, order_quantity, reference="Order", user_id=None, variant_id=None):
        """Deducts raw materials based on recipe for each sold item using atomic consumption."""
        recipe = RecipeService.get_recipe(product_id=product_id, variant_id=variant_id)
        if not recipe or not recipe.items:
            return []

        order_qty_dec = Decimal(str(order_quantity))
        items_reqs = []

        for item in recipe.items:
            ing = item.ingredient
            if not ing:
                continue

            try:
                converted_qty = convert_quantity(item.quantity_required, item.unit, ing.unit)
            except Exception:
                converted_qty = Decimal(str(item.quantity_required))

            items_reqs.append({
                "ingredient_id": ing.id,
                "quantity": converted_qty * order_qty_dec,
                "unit": ing.unit,
                "notes": f"{order_quantity}x {recipe.target_name}"
            })

        return RecipeService.consume_recipe_ingredients(
            items_requirements=items_reqs,
            reference=reference,
            reference_type="SALE",
            user_id=user_id
        )
