from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.modules.inventory.models import (
    Ingredient, StockMovement, StockMovementType, Supplier,
    UnitOfMeasure, InventoryCategory, Purchase, PurchaseItem, PurchaseStatus
)
from app.modules.inventory.validators import (
    validate_inventory_name, validate_inventory_sku, validate_quantity,
    validate_cost, validate_adjustment_reason, validate_supplier
)
from app.modules.auth.models import AuditLog
from app.core.exceptions import NotFoundError, InsufficientStockError, ValidationError
from app.core.pagination import paginate_query
from app.core.utilities import generate_sku


class InventoryService:
    # --- Inventory Item Operations ---

    @staticmethod
    def get_items_paginated(page=1, per_page=15, category_id=None, search=None, stock_status=None, active_only=False):
        query = Ingredient.query
        if active_only:
            query = query.filter_by(is_active=True)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if stock_status == "OUT_OF_STOCK":
            query = query.filter(Ingredient.current_quantity <= Decimal("0.0000"))
        elif stock_status == "LOW_STOCK":
            query = query.filter(
                Ingredient.current_quantity <= Ingredient.reorder_level,
                Ingredient.current_quantity > Decimal("0.0000")
            )
        elif stock_status == "IN_STOCK":
            query = query.filter(Ingredient.current_quantity > Ingredient.reorder_level)

        if search:
            s = f"%{search.strip()}%"
            query = query.filter((Ingredient.name.ilike(s)) | (Ingredient.sku.ilike(s)))

        query = query.order_by(Ingredient.name.asc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_item_by_id(item_id):
        item = db.session.get(Ingredient, item_id)
        if not item:
            raise NotFoundError("Inventory item not found.")
        return item

    # Alias for backward compatibility
    get_ingredient_by_id = get_item_by_id

    @staticmethod
    def get_low_stock_items():
        return Ingredient.query.filter(
            Ingredient.is_active == True,
            Ingredient.current_quantity <= Ingredient.reorder_level
        ).all()

    # Alias for backward compatibility
    get_low_stock_ingredients = get_low_stock_items

    @staticmethod
    def get_low_stock_count():
        return Ingredient.query.filter(
            Ingredient.is_active == True,
            Ingredient.current_quantity <= Ingredient.reorder_level,
            Ingredient.current_quantity > Decimal("0.0000")
        ).count()

    @staticmethod
    def get_out_of_stock_count():
        return Ingredient.query.filter(
            Ingredient.is_active == True,
            Ingredient.current_quantity <= Decimal("0.0000")
        ).count()

    @staticmethod
    def create_item(name, unit_of_measure_id=None, category_id=None, unit="g", initial_quantity=0.0,
                    minimum_stock=10.0, reorder_level=10.0, cost_per_unit=0.0, supplier_id=None,
                    sku=None, description="", maximum_stock=None, user_id=None):
        name = validate_inventory_name(name)

        if not sku or not sku.strip():
            cat_code = "RAW"
            if category_id:
                cat = db.session.get(InventoryCategory, category_id)
                if cat:
                    cat_code = cat.code[:4]
            sku = generate_sku(category_code=cat_code, product_name=name)
            # Ensure unique
            counter = 1
            base_sku = sku
            while Ingredient.query.filter_by(sku=sku).first():
                sku = f"{base_sku}-{counter:02d}"
                counter += 1
        else:
            sku = validate_inventory_sku(sku)

        init_qty = validate_quantity(initial_quantity or Decimal("0.0000"), "Initial Quantity")
        min_stock = validate_quantity(minimum_stock or Decimal("0.0000"), "Minimum Stock")
        reorder_lvl = validate_quantity(reorder_level or min_stock, "Reorder Level")
        max_stock = validate_quantity(maximum_stock, "Maximum Stock") if maximum_stock else None
        cost_unit = validate_cost(cost_per_unit, "Cost Per Unit")

        # Resolve unit string from unit_of_measure if provided
        if unit_of_measure_id:
            uom = db.session.get(UnitOfMeasure, unit_of_measure_id)
            if uom:
                unit = uom.code.lower()

        item = Ingredient(
            name=name,
            sku=sku,
            description=description.strip() if description else "",
            category_id=int(category_id) if category_id else None,
            unit_of_measure_id=int(unit_of_measure_id) if unit_of_measure_id else None,
            unit=unit,
            current_quantity=init_qty,
            minimum_stock_level=min_stock,
            reorder_level=reorder_lvl,
            maximum_stock_level=max_stock,
            cost_per_unit=cost_unit,
            supplier_id=int(supplier_id) if supplier_id else None,
            is_active=True
        )
        db.session.add(item)
        db.session.flush()

        # Log initial movement if initial quantity was provided
        if init_qty > Decimal("0.0000"):
            movement = StockMovement(
                ingredient_id=item.id,
                movement_type=StockMovementType.INITIAL_STOCK,
                quantity=init_qty,
                unit_cost=cost_unit,
                reference_type="INITIALIZATION",
                reference=f"INIT-{item.sku}",
                reason="Initial inventory balance recorded",
                created_by_id=user_id
            )
            db.session.add(movement)

        # Audit Log
        AuditLog.log(
            action="INVENTORY_ITEM_CREATED",
            user_id=user_id,
            details=f"Created inventory item '{item.name}' (SKU: {item.sku}) with initial qty {init_qty} {item.unit}"
        )

        db.session.commit()
        return item

    # Backward compatibility alias
    create_ingredient = create_item

    @staticmethod
    def update_item(item_id, **kwargs):
        item = InventoryService.get_item_by_id(item_id)

        if "name" in kwargs and kwargs["name"]:
            name = kwargs["name"].strip()
            if name != item.name:
                item.name = validate_inventory_name(name, exclude_id=item.id)

        if "category_id" in kwargs:
            item.category_id = int(kwargs["category_id"]) if kwargs["category_id"] else None

        if "unit_of_measure_id" in kwargs and kwargs["unit_of_measure_id"]:
            uom_id = int(kwargs["unit_of_measure_id"])
            uom = db.session.get(UnitOfMeasure, uom_id)
            if uom:
                item.unit_of_measure_id = uom.id
                item.unit = uom.code.lower()

        if "unit" in kwargs and kwargs["unit"]:
            item.unit = kwargs["unit"]

        if "minimum_stock" in kwargs and kwargs["minimum_stock"] is not None:
            item.minimum_stock_level = validate_quantity(kwargs["minimum_stock"], "Minimum Stock")

        if "reorder_level" in kwargs and kwargs["reorder_level"] is not None:
            item.reorder_level = validate_quantity(kwargs["reorder_level"], "Reorder Level")

        if "maximum_stock" in kwargs and kwargs["maximum_stock"] is not None:
            item.maximum_stock_level = validate_quantity(kwargs["maximum_stock"], "Maximum Stock")

        if "cost_per_unit" in kwargs and kwargs["cost_per_unit"] is not None:
            item.cost_per_unit = validate_cost(kwargs["cost_per_unit"], "Cost Per Unit")

        if "supplier_id" in kwargs:
            item.supplier_id = int(kwargs["supplier_id"]) if kwargs["supplier_id"] else None

        if "description" in kwargs and kwargs["description"] is not None:
            item.description = kwargs["description"].strip()

        if "is_active" in kwargs and kwargs["is_active"] is not None:
            item.is_active = bool(kwargs["is_active"])

        item.updated_at = datetime.utcnow()

        AuditLog.log(
            action="INVENTORY_ITEM_UPDATED",
            details=f"Updated inventory item '{item.name}' (SKU: {item.sku})"
        )

        db.session.commit()
        return item

    # Backward compatibility alias
    update_ingredient = update_item

    # --- Atomic Stock Movements & Adjustments ---

    @staticmethod
    def adjust_stock(item_id, quantity, reason, reference="", notes="", user_id=None):
        """
        Execute an atomic stock adjustment with row-level locking.
        Prevents negative stock and enforces mandatory adjustment reason.
        """
        reason = validate_adjustment_reason(reason)
        qty = validate_quantity(quantity, "Adjustment Quantity", allow_negative=True)

        if qty == Decimal("0.0000"):
            raise ValidationError("Adjustment quantity cannot be zero.")

        # Lock item row for update to prevent concurrent race conditions
        item = db.session.query(Ingredient).filter_by(id=item_id).with_for_update().first()
        if not item:
            raise NotFoundError("Inventory item not found.")

        new_stock = item.current_quantity + qty
        if new_stock < Decimal("0.0000"):
            raise InsufficientStockError(
                f"Insufficient stock for {item.name}. Current balance is {item.current_quantity} {item.unit}; "
                f"cannot reduce by {abs(qty)} {item.unit} (would result in {new_stock} {item.unit})."
            )

        item.current_quantity = new_stock
        item.updated_at = datetime.utcnow()

        movement_type = StockMovementType.ADJUSTMENT_IN if qty > Decimal("0.0000") else StockMovementType.ADJUSTMENT_OUT

        ref_str = reference.strip() if reference else f"ADJ-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        movement = StockMovement(
            ingredient_id=item.id,
            movement_type=movement_type,
            quantity=qty,
            unit_cost=item.cost_per_unit,
            reference_type="MANUAL_ADJUSTMENT",
            reference=ref_str,
            reason=reason,
            notes=notes.strip() if notes else None,
            created_by_id=user_id
        )
        db.session.add(movement)

        AuditLog.log(
            action="STOCK_ADJUSTED",
            user_id=user_id,
            details=f"Adjusted stock for '{item.name}' by {qty:+f} {item.unit}. Reason: {reason}. New balance: {item.current_quantity} {item.unit}."
        )

        db.session.commit()
        return movement

    @staticmethod
    def record_movement(ingredient_id, movement_type, quantity, reference="", notes="", reason="", user_id=None):
        """
        Transactional movement recorder supporting purchase, adjustment, waste, consumption.
        Ensures stock balance and movement ledger stay synchronized.
        """
        qty = validate_quantity(quantity, "Movement Quantity", allow_negative=True)

        # Lock item row
        item = db.session.query(Ingredient).filter_by(id=ingredient_id).with_for_update().first()
        if not item:
            raise NotFoundError("Inventory item not found.")

        # Determine direction and validation
        if movement_type in (StockMovementType.CONSUMPTION, StockMovementType.WASTE, StockMovementType.ADJUSTMENT_OUT):
            if qty > Decimal("0.0000"):
                qty = -qty  # ensure negative
            if (item.current_quantity + qty) < Decimal("0.0000"):
                raise InsufficientStockError(
                    f"Insufficient stock for {item.name}. Current stock: {item.current_quantity} {item.unit}."
                )
        elif movement_type in (StockMovementType.PURCHASE, StockMovementType.ADJUSTMENT_IN, StockMovementType.INITIAL_STOCK):
            qty = abs(qty)

        item.current_quantity += qty
        item.updated_at = datetime.utcnow()

        movement = StockMovement(
            ingredient_id=item.id,
            movement_type=movement_type,
            quantity=qty,
            unit_cost=item.cost_per_unit,
            reference=reference,
            reason=reason if reason else f"{movement_type.capitalize()} logged",
            notes=notes,
            created_by_id=user_id
        )
        db.session.add(movement)
        db.session.commit()
        return movement

    # --- Unit of Measure & Category Operations ---

    @staticmethod
    def get_units_of_measure():
        return UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name.asc()).all()

    @staticmethod
    def get_inventory_categories():
        return InventoryCategory.query.filter_by(is_active=True).order_by(
            InventoryCategory.display_order.asc(), InventoryCategory.name.asc()
        ).all()

    # --- Supplier Operations ---

    @staticmethod
    def get_suppliers():
        return Supplier.query.filter_by(is_active=True).order_by(Supplier.name.asc()).all()

    @staticmethod
    def get_supplier_by_id(supplier_id):
        supplier = db.session.get(Supplier, supplier_id)
        if not supplier:
            raise NotFoundError("Supplier not found.")
        return supplier

    @staticmethod
    def create_supplier(name, contact_person="", email=None, phone="", address="", notes=""):
        name = validate_supplier(name, email=email, phone=phone)
        supplier = Supplier(
            name=name,
            contact_person=contact_person.strip() if contact_person else None,
            email=email.strip().lower() if email else None,
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            notes=notes.strip() if notes else None,
            is_active=True
        )
        db.session.add(supplier)
        AuditLog.log(action="SUPPLIER_CREATED", details=f"Created supplier '{supplier.name}'")
        db.session.commit()
        return supplier

    @staticmethod
    def update_supplier(supplier_id, **kwargs):
        supplier = InventoryService.get_supplier_by_id(supplier_id)
        if "name" in kwargs and kwargs["name"]:
            supplier.name = validate_supplier(
                kwargs["name"],
                email=kwargs.get("email"),
                phone=kwargs.get("phone"),
                exclude_id=supplier.id
            )
        if "contact_person" in kwargs:
            supplier.contact_person = kwargs["contact_person"].strip() if kwargs["contact_person"] else None
        if "email" in kwargs:
            supplier.email = kwargs["email"].strip().lower() if kwargs["email"] else None
        if "phone" in kwargs:
            supplier.phone = kwargs["phone"].strip() if kwargs["phone"] else None
        if "address" in kwargs:
            supplier.address = kwargs["address"].strip() if kwargs["address"] else None
        if "notes" in kwargs:
            supplier.notes = kwargs["notes"].strip() if kwargs["notes"] else None
        if "is_active" in kwargs:
            supplier.is_active = bool(kwargs["is_active"])

        supplier.updated_at = datetime.utcnow()
        AuditLog.log(action="SUPPLIER_UPDATED", details=f"Updated supplier '{supplier.name}'")
        db.session.commit()
        return supplier

    # --- Purchase Orders & Stock In ---

    @staticmethod
    def get_purchases_paginated(page=1, per_page=15, status=None):
        query = Purchase.query
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(Purchase.created_at.desc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_purchase_by_id(purchase_id):
        purchase = db.session.get(Purchase, purchase_id)
        if not purchase:
            raise NotFoundError("Purchase order not found.")
        return purchase

    @staticmethod
    def create_purchase(supplier_id, reference_number, items_data, notes="", user_id=None):
        """
        Create a purchase record in DRAFT status. Does NOT alter inventory until received.
        """
        supplier = InventoryService.get_supplier_by_id(supplier_id)
        if not reference_number or not reference_number.strip():
            reference_number = f"PO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        else:
            reference_number = reference_number.strip().upper()

        if Purchase.query.filter_by(reference_number=reference_number).first():
            raise ValidationError(f"Purchase reference number '{reference_number}' already exists.")

        if not items_data or not isinstance(items_data, list):
            raise ValidationError("At least one purchase line item is required.")

        purchase = Purchase(
            supplier_id=supplier.id,
            reference_number=reference_number,
            status=PurchaseStatus.DRAFT,
            notes=notes.strip() if notes else None,
            created_by_id=user_id,
            total_cost=Decimal("0.00")
        )
        db.session.add(purchase)
        db.session.flush()

        total_cost = Decimal("0.00")
        for item_data in items_data:
            ing_id = int(item_data.get("ingredient_id"))
            ingredient = db.session.get(Ingredient, ing_id)
            if not ingredient:
                raise NotFoundError(f"Inventory item ID {ing_id} not found.")

            qty = validate_quantity(item_data.get("quantity"), f"Quantity for {ingredient.name}")
            if qty <= Decimal("0.0000"):
                raise ValidationError(f"Quantity for {ingredient.name} must be greater than zero.")

            unit_cost = validate_cost(item_data.get("unit_cost"), f"Cost for {ingredient.name}")
            line_total = (qty * unit_cost).quantize(Decimal("0.01"))
            total_cost += line_total

            p_item = PurchaseItem(
                purchase_id=purchase.id,
                ingredient_id=ingredient.id,
                quantity=qty,
                unit_cost=unit_cost,
                line_total=line_total
            )
            db.session.add(p_item)

        purchase.total_cost = total_cost

        AuditLog.log(
            action="PURCHASE_CREATED",
            user_id=user_id,
            details=f"Created PO '{purchase.reference_number}' for {supplier.name} (Total: {purchase.total_cost})"
        )

        db.session.commit()
        return purchase

    @staticmethod
    def receive_purchase(purchase_id, user_id=None):
        """
        Atomically transitions purchase from DRAFT to RECEIVED,
        increments inventory quantities, and records immutable StockMovement entries.
        """
        purchase = db.session.query(Purchase).filter_by(id=purchase_id).with_for_update().first()
        if not purchase:
            raise NotFoundError("Purchase order not found.")

        if purchase.status == PurchaseStatus.RECEIVED:
            raise ValidationError(f"Purchase '{purchase.reference_number}' has already been received.")
        if purchase.status == PurchaseStatus.CANCELLED:
            raise ValidationError(f"Cannot receive cancelled purchase '{purchase.reference_number}'.")

        # Process each item atomically
        for p_item in purchase.items:
            # Lock the ingredient row
            ingredient = db.session.query(Ingredient).filter_by(id=p_item.ingredient_id).with_for_update().first()
            if not ingredient:
                continue

            ingredient.current_quantity += p_item.quantity
            # Update item cost per unit if provided
            if p_item.unit_cost > Decimal("0.0000"):
                ingredient.cost_per_unit = p_item.unit_cost
            ingredient.updated_at = datetime.utcnow()

            # Record immutable Stock Movement
            movement = StockMovement(
                ingredient_id=ingredient.id,
                movement_type=StockMovementType.PURCHASE,
                quantity=p_item.quantity,
                unit_cost=p_item.unit_cost,
                reference_type="PURCHASE_ORDER",
                reference_id=purchase.id,
                reference=purchase.reference_number,
                reason=f"Received via PO {purchase.reference_number}",
                notes=f"Supplier: {purchase.supplier.name}",
                created_by_id=user_id
            )
            db.session.add(movement)

        purchase.status = PurchaseStatus.RECEIVED
        purchase.updated_at = datetime.utcnow()

        AuditLog.log(
            action="STOCK_RECEIVED",
            user_id=user_id,
            details=f"Received stock for PO '{purchase.reference_number}'. Increased inventory for {purchase.items.count()} items."
        )

        db.session.commit()
        return purchase

    @staticmethod
    def cancel_purchase(purchase_id, user_id=None):
        """Safely cancel a purchase order."""
        purchase = db.session.query(Purchase).filter_by(id=purchase_id).with_for_update().first()
        if not purchase:
            raise NotFoundError("Purchase order not found.")

        if purchase.status == PurchaseStatus.CANCELLED:
            return purchase

        if purchase.status == PurchaseStatus.RECEIVED:
            # Reversal requires compensating movement (CORRECTION)
            for p_item in purchase.items:
                ingredient = db.session.query(Ingredient).filter_by(id=p_item.ingredient_id).with_for_update().first()
                if not ingredient:
                    continue
                if ingredient.current_quantity < p_item.quantity:
                    raise ValidationError(
                        f"Cannot cancel purchase: insufficient stock of {ingredient.name} remaining to reverse."
                    )
                ingredient.current_quantity -= p_item.quantity
                ingredient.updated_at = datetime.utcnow()

                movement = StockMovement(
                    ingredient_id=ingredient.id,
                    movement_type=StockMovementType.CORRECTION,
                    quantity=-p_item.quantity,
                    unit_cost=p_item.unit_cost,
                    reference_type="PURCHASE_CANCELLATION",
                    reference_id=purchase.id,
                    reference=f"CANCEL-{purchase.reference_number}",
                    reason=f"Compensating deduction for cancelled PO {purchase.reference_number}",
                    created_by_id=user_id
                )
                db.session.add(movement)

        purchase.status = PurchaseStatus.CANCELLED
        purchase.updated_at = datetime.utcnow()

        AuditLog.log(
            action="PURCHASE_CANCELLED",
            user_id=user_id,
            details=f"Cancelled purchase '{purchase.reference_number}'."
        )

        db.session.commit()
        return purchase

    # --- Dashboard & Statistics ---

    @staticmethod
    def get_inventory_stats():
        total_items = Ingredient.query.filter_by(is_active=True).count()
        low_stock = InventoryService.get_low_stock_count()
        out_of_stock = InventoryService.get_out_of_stock_count()
        active_suppliers = Supplier.query.filter_by(is_active=True).count()

        # Calculate inventory valuation: sum(current_quantity * cost_per_unit)
        items = Ingredient.query.filter_by(is_active=True).all()
        total_value = sum(item.current_quantity * item.cost_per_unit for item in items)

        return {
            "total_items": total_items,
            "low_stock_count": low_stock,
            "out_of_stock_count": out_of_stock,
            "active_suppliers_count": active_suppliers,
            "total_value": float(total_value)
        }
