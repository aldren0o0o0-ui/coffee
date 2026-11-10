from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.modules.pos.models import POSRegisterShift
from app.modules.pos.validators import validate_no_active_shift
from app.modules.sales.models import Sale, SaleItem, Payment, SaleStatus, PaymentStatus, PaymentMethod
from app.modules.catalog.models import Product, ProductVariant, ProductOption
from app.modules.recipes.services import RecipeService
from app.core.exceptions import NotFoundError, ValidationError, InsufficientStockError
from app.core.utilities import generate_invoice_number, format_currency


class POSService:
    @staticmethod
    def get_active_shift(user_id):
        return POSRegisterShift.query.filter_by(user_id=user_id, is_active=True).first()

    @staticmethod
    def open_shift(user_id, opening_cash=0.0, notes=""):
        validate_no_active_shift(user_id)
        shift = POSRegisterShift(
            user_id=user_id,
            opening_cash=Decimal(str(opening_cash or "0.00")),
            notes=notes.strip() if notes else "",
            is_active=True
        )
        db.session.add(shift)
        db.session.commit()
        return shift

    @staticmethod
    def close_shift(shift_id, closing_cash, notes=""):
        shift = db.session.get(POSRegisterShift, shift_id)
        if not shift or not shift.is_active:
            raise NotFoundError("Active shift not found.")

        closing_val = Decimal(str(closing_cash or "0.00"))
        # Expected cash in drawer = opening cash + total cash sales
        # Note: Non-cash payments (Card, QR) do not enter physical cash drawer
        cash_sales_sum = db.session.query(db.func.coalesce(db.func.sum(Sale.total_amount), 0)).filter(
            Sale.shift_id == shift.id,
            Sale.payment_method == PaymentMethod.CASH,
            Sale.status == SaleStatus.COMPLETED
        ).scalar()
        expected = Decimal(str(shift.opening_cash or "0.00")) + Decimal(str(cash_sales_sum))

        shift.closing_cash = closing_val
        shift.expected_cash = expected
        shift.closed_at = datetime.utcnow()
        shift.is_active = False
        if notes:
            shift.notes = f"{shift.notes} | Close Note: {notes}" if shift.notes else notes
        db.session.commit()
        return shift

    @staticmethod
    def checkout(user_id, items_data, payment_method="Cash", cash_tendered=0.0,
                 customer_name="Guest", discount_amount=0.0, notes="", tax_rate=0.08,
                 idempotency_key=None):
        """
        Server-Authoritative POS Checkout with Atomic Recipe Stock Deduction.
        Guarantees:
        1. Never trust browser prices; compute all line items from DB.
        2. Atomic raw material deduction: EITHER all ingredients deducted OR none.
        3. Idempotent: duplicate requests return existing sale receipt without re-deducting.
        """
        if not items_data or len(items_data) == 0:
            raise ValidationError("Cannot checkout an empty cart.")

        # 1. Idempotency Check
        if idempotency_key:
            idempotency_key = str(idempotency_key).strip()
            existing_sale = Sale.query.filter_by(idempotency_key=idempotency_key).first()
            if existing_sale:
                return existing_sale

        active_shift = POSRegisterShift.query.filter_by(user_id=user_id, is_active=True).first()

        # 2. Authoritative Validation & Pricing
        validated_items = []
        raw_materials_needed = []
        subtotal = Decimal("0.00")

        for idx, item in enumerate(items_data, 1):
            p_id = item.get("product_id")
            if not p_id:
                raise ValidationError(f"Cart item #{idx} missing product reference.")
            try:
                p_id = int(p_id)
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid product_id in cart item #{idx}.")

            product = db.session.get(Product, p_id)
            if not product or not product.is_active or not product.is_available:
                raise ValidationError(f"Product '{product.name if product else p_id}' is unavailable.")

            try:
                qty = int(item.get("quantity", 1))
                if qty <= 0:
                    raise ValidationError(f"Quantity for '{product.name}' must be at least 1.")
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid quantity for '{product.name}'.")

            # Check Variant if provided
            v_id = item.get("variant_id")
            variant = None
            variant_name = None
            if v_id:
                try:
                    v_id = int(v_id)
                    variant = db.session.get(ProductVariant, v_id)
                    if not variant or not variant.is_active or not variant.is_available:
                        raise ValidationError(f"Variant for '{product.name}' is unavailable.")
                    if variant.product_id != product.id:
                        raise ValidationError(f"Variant '{variant.name}' does not belong to '{product.name}'.")
                    variant_name = variant.name
                except (ValueError, TypeError):
                    raise ValidationError("Invalid variant_id.")

            # Base unit price and cost (Variant overrides Product)
            if variant:
                base_unit_price = Decimal(str(variant.price))
                base_unit_cost = Decimal(str(variant.cost_price or product.cost_price or "0.00"))
            else:
                base_unit_price = Decimal(str(product.base_price))
                base_unit_cost = Decimal(str(product.cost_price or "0.00"))

            # Process Options / Modifiers
            options_data = []
            options_price = Decimal("0.00")
            raw_options = item.get("options") or item.get("option_ids") or []
            if raw_options:
                for opt_ref in raw_options:
                    opt_id = opt_ref.get("id") if isinstance(opt_ref, dict) else opt_ref
                    try:
                        opt_id = int(opt_id)
                    except (ValueError, TypeError):
                        continue
                    opt = db.session.get(ProductOption, opt_id)
                    if opt and opt.is_available:
                        opt_adj = Decimal(str(opt.price_adjustment or "0.00"))
                        options_price += opt_adj
                        options_data.append({
                            "id": opt.id,
                            "group_id": opt.group_id,
                            "name": opt.name,
                            "price_adjustment": float(opt_adj)
                        })

            line_unit_price = base_unit_price + options_price
            line_subtotal = line_unit_price * Decimal(str(qty))
            subtotal += line_subtotal

            validated_items.append({
                "product": product,
                "variant": variant,
                "variant_id": variant.id if variant else None,
                "variant_name": variant_name,
                "options_data": options_data if options_data else None,
                "options_price": options_price,
                "unit_price": line_unit_price,
                "unit_cost": base_unit_cost,
                "quantity": qty,
                "subtotal": line_subtotal
            })

            # Check Recipe for this product/variant
            recipe = RecipeService.get_recipe(product_id=product.id, variant_id=variant.id if variant else None)
            if recipe and recipe.is_active:
                for r_item in recipe.items:
                    needed_qty = Decimal(str(r_item.quantity_required)) * Decimal(str(qty))
                    raw_materials_needed.append({
                        "ingredient_id": r_item.ingredient_id,
                        "quantity": needed_qty,
                        "unit": r_item.unit or (r_item.ingredient.unit if r_item.ingredient else None),
                        "notes": f"{product.name}{' (' + variant_name + ')' if variant_name else ''} x{qty}"
                    })

        # 3. Server-Authoritative Totals Calculation
        discount_dec = min(Decimal(str(discount_amount or "0.00")), subtotal)
        taxable_amount = max(subtotal - discount_dec, Decimal("0.00"))
        tax_rate_dec = Decimal(str(tax_rate or "0.00"))
        tax = (taxable_amount * tax_rate_dec).quantize(Decimal("0.01"))
        total = (taxable_amount + tax).quantize(Decimal("0.01"))

        # Cash change calculation
        cash_tendered_dec = Decimal(str(cash_tendered or "0.00"))
        change_due_dec = Decimal("0.00")
        if payment_method == PaymentMethod.CASH or payment_method == "Cash":
            if cash_tendered_dec < total:
                raise ValidationError(
                    f"Cash tendered ({format_currency(cash_tendered_dec)}) is less than total amount ({format_currency(total)})."
                )
            change_due_dec = (cash_tendered_dec - total).quantize(Decimal("0.01"))
        else:
            cash_tendered_dec = total
            change_due_dec = Decimal("0.00")

        # 4. ATOMIC TRANSACTION EXECUTION
        try:
            invoice_no = generate_invoice_number(prefix="COF")

            sale = Sale(
                invoice_no=invoice_no,
                idempotency_key=idempotency_key,
                user_id=user_id,
                shift_id=active_shift.id if active_shift else None,
                customer_name=customer_name.strip() if customer_name else "Guest",
                subtotal_amount=subtotal.quantize(Decimal("0.01")),
                tax_amount=tax,
                discount_amount=discount_dec.quantize(Decimal("0.01")),
                total_amount=total,
                payment_method=payment_method,
                cash_tendered=cash_tendered_dec,
                change_due=change_due_dec,
                status=SaleStatus.COMPLETED,
                notes=notes.strip() if notes else None
            )
            db.session.add(sale)
            db.session.flush()

            for v in validated_items:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=v["product"].id,
                    variant_id=v["variant_id"],
                    product_name=v["product"].name,
                    variant_name=v["variant_name"],
                    options_data=v["options_data"],
                    options_price=v["options_price"].quantize(Decimal("0.01")),
                    unit_price=v["unit_price"].quantize(Decimal("0.01")),
                    unit_cost=v["unit_cost"].quantize(Decimal("0.01")),
                    quantity=v["quantity"],
                    subtotal=v["subtotal"].quantize(Decimal("0.01"))
                )
                db.session.add(sale_item)

            # Create authoritative Payment record
            payment = Payment(
                sale_id=sale.id,
                payment_method=payment_method,
                amount=total,
                status=PaymentStatus.SUCCESS,
                cash_tendered=cash_tendered_dec if (payment_method == PaymentMethod.CASH or payment_method == "Cash") else None,
                change_due=change_due_dec if (payment_method == PaymentMethod.CASH or payment_method == "Cash") else None,
                created_by_id=user_id,
                created_at=datetime.utcnow()
            )
            db.session.add(payment)

            # Atomic Recipe Consumption (locks rows and verifies stock)
            if raw_materials_needed:
                RecipeService.consume_recipe_ingredients(
                    items_requirements=raw_materials_needed,
                    reference=f"Sale #{invoice_no}",
                    reference_type="SALE",
                    reference_id=sale.id,
                    user_id=user_id
                )

            # Update Shift totals
            if active_shift:
                active_shift.total_sales_amount = (
                    Decimal(str(active_shift.total_sales_amount or "0.00")) + total
                ).quantize(Decimal("0.01"))
                active_shift.total_orders_count = (active_shift.total_orders_count or 0) + 1

            db.session.commit()
            return sale

        except Exception:
            db.session.rollback()
            raise

