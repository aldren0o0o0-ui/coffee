"""Database seeder populating realistic demo data for a Coffee Shop SME (Phase 1 to Phase 4)."""
import sys
import os
from decimal import Decimal
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.modules.users.models import User
from app.core.permissions import Roles
from app.modules.catalog.models import Category, Product, ProductVariant
from app.modules.inventory.models import (
    Supplier, Ingredient, StockMovement, StockMovementType,
    UnitOfMeasure, InventoryCategory, Purchase, PurchaseItem, PurchaseStatus
)
from app.modules.settings.models import StoreSetting
from app.modules.settings.services import DEFAULT_SETTINGS
from app.modules.catalog.validators import slugify


def seed():
    app = create_app()
    with app.app_context():
        print("[*] Seeding Coffee Shop SME database (Phases 1 - 4)...")

        # 1. Store Settings
        for k, v in DEFAULT_SETTINGS.items():
            if not StoreSetting.query.filter_by(key=k).first():
                db.session.add(StoreSetting(key=k, value=v))
        db.session.commit()

        # 2. Users (All 5 Standard Roles: Owner, Manager, Cashier, Barista, Staff)
        demo_users = [
            ("owner", "owner@coffee.local", "Elena", "Vance", Roles.OWNER, "OwnerPass123!"),
            ("manager", "manager@coffee.local", "Marco", "Silva", Roles.MANAGER, "ManagerPass123!"),
            ("cashier", "cashier@coffee.local", "Leo", "Brooks", Roles.CASHIER, "CashierPass123!"),
            ("barista", "barista@coffee.local", "Aria", "Chen", Roles.BARISTA, "BaristaPass123!"),
            ("staff", "staff@coffee.local", "David", "Kim", Roles.STAFF, "StaffPass123!"),
        ]
        users_map = {}
        for username, email, first_name, last_name, role, pwd in demo_users:
            u = User.query.filter_by(username=username).first()
            if not u:
                u = User(username=username, email=email, first_name=first_name, last_name=last_name, role=role, is_active=True)
                u.set_password(pwd)
                db.session.add(u)
                db.session.flush()
            else:
                u.first_name = first_name
                u.last_name = last_name
                u.role = role
                u.is_active = True
                u.set_password(pwd)
            users_map[role] = u
        db.session.commit()

        # 3. Units of Measure
        uom_data = [
            ("KG", "Kilogram", "WEIGHT"),
            ("G", "Gram", "WEIGHT"),
            ("L", "Liter", "VOLUME"),
            ("ML", "Milliliter", "VOLUME"),
            ("PCS", "Pieces", "COUNT"),
            ("PACK", "Pack", "PACKAGING"),
            ("BOX", "Box", "PACKAGING"),
            ("BOTTLE", "Bottle", "PACKAGING"),
        ]
        uom_map = {}
        for code, name, cat in uom_data:
            u = UnitOfMeasure.query.filter_by(code=code).first()
            if not u:
                u = UnitOfMeasure(code=code, name=name, category=cat, is_active=True)
                db.session.add(u)
                db.session.flush()
            uom_map[code] = u
        db.session.commit()

        # 4. Inventory Raw Material Categories
        inv_cat_data = [
            ("Coffee Beans", "BEANS", "Whole bean and roasted coffee", 1),
            ("Milk & Dairy", "DAIRY", "Fresh milk, plant-based milk and cream", 2),
            ("Syrups & Flavoring", "SYRUPS", "Flavored beverage syrups and sauces", 3),
            ("Tea & Powders", "TEA", "Loose tea, matcha and chocolate powders", 4),
            ("Sweeteners", "SWEET", "Sugar, honey and syrups", 5),
            ("Packaging & Disposables", "PACK", "Cups, lids, straws and takeout bags", 6),
            ("Cleaning & Consumables", "CLEAN", "Filter papers and cleaning chemicals", 7),
        ]
        inv_cat_map = {}
        for name, code, desc, order in inv_cat_data:
            ic = InventoryCategory.query.filter_by(code=code).first()
            if not ic:
                ic = InventoryCategory(name=name, code=code, description=desc, display_order=order, is_active=True)
                db.session.add(ic)
                db.session.flush()
            inv_cat_map[code] = ic
        db.session.commit()

        # 5. Suppliers
        suppliers_data = [
            ("Altitude Coffee Importers", "Mateo Gomez", "mateo@altitudecoffee.com", "+1-555-0199", "128 Roast Way, Seattle"),
            ("Valley Dairy Farms", "Sarah Jenkins", "orders@valleydairy.com", "+1-555-0144", "45 Farm Road, Portland"),
            ("EcoPackaging Solutions", "Liam Davis", "sales@ecopack.com", "+1-555-0182", "99 Harbor Blvd, San Francisco"),
        ]
        suppliers_map = {}
        for name, cp, em, ph, addr in suppliers_data:
            s = Supplier.query.filter_by(name=name).first()
            if not s:
                s = Supplier(name=name, contact_person=cp, email=em, phone=ph, address=addr, is_active=True)
                db.session.add(s)
                db.session.flush()
            suppliers_map[name] = s
        db.session.commit()

        # 6. Raw Material Ingredients
        raw_materials = [
            ("Specialty Espresso Blend (Beans)", "RAW-BEAN-01", "G", "BEANS", Decimal("5000.0000"), Decimal("1000.0000"), Decimal("1500.0000"), Decimal("1.2500"), "Altitude Coffee Importers"),
            ("Whole Dairy Milk", "RAW-MILK-01", "ML", "DAIRY", Decimal("20000.0000"), Decimal("3000.0000"), Decimal("5000.0000"), Decimal("0.0800"), "Valley Dairy Farms"),
            ("Oat Milk (Barista Edition)", "RAW-OAT-01", "ML", "DAIRY", Decimal("12000.0000"), Decimal("2000.0000"), Decimal("4000.0000"), Decimal("0.1600"), "Valley Dairy Farms"),
            ("Organic Vanilla Syrup", "RAW-SYR-VAN", "ML", "SYRUPS", Decimal("2500.0000"), Decimal("500.0000"), Decimal("800.0000"), Decimal("0.7500"), "Altitude Coffee Importers"),
            ("Artisan Caramel Drizzle", "RAW-SYR-CAR", "ML", "SYRUPS", Decimal("2000.0000"), Decimal("400.0000"), Decimal("600.0000"), Decimal("0.9000"), "Altitude Coffee Importers"),
            ("Ceremonial Uji Matcha", "RAW-MAT-01", "G", "TEA", Decimal("800.0000"), Decimal("200.0000"), Decimal("300.0000"), Decimal("4.2500"), "Altitude Coffee Importers"),
            ("Compostable 12oz Cups", "RAW-CUP-12", "PCS", "PACK", Decimal("600.0000"), Decimal("150.0000"), Decimal("250.0000"), Decimal("6.0000"), "EcoPackaging Solutions"),
            ("Eco Sip Lids 12oz", "RAW-LID-12", "PCS", "PACK", Decimal("650.0000"), Decimal("150.0000"), Decimal("250.0000"), Decimal("2.5000"), "EcoPackaging Solutions"),
        ]
        ingredients_map = {}
        for name, sku, uom_code, cat_code, stock, min_stock, reorder_lvl, cpu, sup_name in raw_materials:
            ing = Ingredient.query.filter_by(sku=sku).first()
            if not ing:
                ing = Ingredient(
                    name=name,
                    sku=sku,
                    unit_of_measure_id=uom_map[uom_code].id,
                    unit=uom_code.lower(),
                    category_id=inv_cat_map[cat_code].id,
                    current_quantity=stock,
                    minimum_stock_level=min_stock,
                    reorder_level=reorder_lvl,
                    cost_per_unit=cpu,
                    supplier_id=suppliers_map[sup_name].id,
                    is_active=True
                )
                db.session.add(ing)
                db.session.flush()

                # Log initial movement
                db.session.add(StockMovement(
                    ingredient_id=ing.id,
                    movement_type=StockMovementType.INITIAL_STOCK,
                    quantity=stock,
                    unit_cost=cpu,
                    reference_type="INITIALIZATION",
                    reference=f"INIT-{ing.sku}",
                    reason="Initial stocktake baseline",
                    created_by_id=users_map[Roles.OWNER].id
                ))
            ingredients_map[name] = ing
        db.session.commit()

        # 7. Menu Categories
        categories_data = [
            ("Espresso Bar", "Handcrafted signature espresso drinks", 1),
            ("Brewed & Cold", "Single origin filter and cold brews", 2),
            ("Tea & Alternatives", "Artisan matcha, chai, and herbal drinks", 3),
            ("Bakery & Pastries", "Fresh daily artisanal baked goods", 4),
            ("Retail Beans", "Whole bean bags roasted in-house", 5),
        ]
        cat_map = {}
        for name, desc, order in categories_data:
            c = Category.query.filter_by(name=name).first()
            if not c:
                c = Category(
                    name=name,
                    slug=slugify(name),
                    description=desc,
                    display_order=order,
                    is_active=True
                )
                db.session.add(c)
                db.session.flush()
            cat_map[name] = c
        db.session.commit()

        # 8. Menu Products & Variants
        products_data = [
            ("Espresso Bar", "Double Espresso", "COF-ESP-001", Decimal("120.00"), Decimal("22.50"),
             "Double shot extracted from our signature roast",
             [("Solo Shot", "COF-ESP-001-S", Decimal("90.00"), Decimal("11.25")),
              ("Double Shot", "COF-ESP-001-D", Decimal("120.00"), Decimal("22.50"))]),

            ("Espresso Bar", "Caffe Latte", "COF-LAT-001", Decimal("165.00"), Decimal("42.00"),
             "Rich espresso with velvety steamed whole milk",
             [("12oz Hot", "COF-LAT-001-12H", Decimal("165.00"), Decimal("42.00")),
              ("16oz Iced", "COF-LAT-001-16I", Decimal("185.00"), Decimal("48.00"))]),

            ("Espresso Bar", "Spanish Latte", "COF-SPL-001", Decimal("180.00"), Decimal("45.00"),
             "Espresso with sweetened condensed and steamed whole milk",
             [("12oz Hot", "COF-SPL-001-12H", Decimal("180.00"), Decimal("45.00")),
              ("16oz Iced", "COF-SPL-001-16I", Decimal("195.00"), Decimal("52.00"))]),

            ("Brewed & Cold", "Cold Brew Coffee", "COL-BRW-001", Decimal("150.00"), Decimal("31.00"),
             "Slow-steeped for 18 hours, smooth chocolate profile", []),

            ("Tea & Alternatives", "Iced Uji Matcha Latte", "TEA-MAT-001", Decimal("190.00"), Decimal("55.00"),
             "Authentic ceremonial matcha whisked with fresh milk",
             [("12oz Regular", "TEA-MAT-001-12", Decimal("190.00"), Decimal("55.00")),
              ("16oz Large", "TEA-MAT-001-16", Decimal("210.00"), Decimal("65.00"))]),

            ("Bakery & Pastries", "Artisan Butter Croissant", "BAK-CRS-001", Decimal("135.00"), Decimal("50.00"),
             "Flaky French butter pastry baked fresh every morning", []),
        ]

        for cat_name, prod_name, sku, price, cost, desc, variants in products_data:
            p = Product.query.filter_by(sku=sku).first()
            if not p:
                p = Product(
                    name=prod_name,
                    slug=slugify(prod_name),
                    sku=sku,
                    category_id=cat_map[cat_name].id,
                    base_price=price,
                    cost_price=cost,
                    description=desc,
                    is_available=True,
                    is_active=True
                )
                db.session.add(p)
                db.session.flush()

                for v_idx, (v_name, v_sku, v_price, v_cost) in enumerate(variants):
                    v = ProductVariant(
                        product_id=p.id,
                        name=v_name,
                        sku=v_sku,
                        price=v_price,
                        cost_price=v_cost,
                        is_available=True,
                        is_active=True,
                        display_order=v_idx
                    )
                    db.session.add(v)

        db.session.commit()

        # 9. Sample Purchases (1 RECEIVED, 1 DRAFT)
        if Purchase.query.count() == 0:
            po1 = Purchase(
                supplier_id=suppliers_map["Altitude Coffee Importers"].id,
                reference_number="PO-2026-09-001",
                purchase_date=datetime.utcnow() - timedelta(days=2),
                status=PurchaseStatus.RECEIVED,
                total_cost=Decimal("6250.00"),
                notes="Bi-weekly whole bean shipment received and inspected",
                created_by_id=users_map[Roles.OWNER].id
            )
            db.session.add(po1)
            db.session.flush()

            db.session.add(PurchaseItem(
                purchase_id=po1.id,
                ingredient_id=ingredients_map["Specialty Espresso Blend (Beans)"].id,
                quantity=Decimal("5000.0000"),
                unit_cost=Decimal("1.2500"),
                line_total=Decimal("6250.00")
            ))

            po2 = Purchase(
                supplier_id=suppliers_map["Valley Dairy Farms"].id,
                reference_number="PO-2026-09-002",
                purchase_date=datetime.utcnow(),
                status=PurchaseStatus.DRAFT,
                total_cost=Decimal("1600.00"),
                notes="Pending delivery tomorrow morning",
                created_by_id=users_map[Roles.MANAGER].id
            )
            db.session.add(po2)
            db.session.flush()

        # 10. Product Option Groups & Modifiers (Phase 6)
        from app.modules.catalog.models import ProductOptionGroup, ProductOption
        from app.modules.recipes.models import Recipe, RecipeItem
        from app.modules.pos.models import POSRegisterShift
        from app.modules.sales.models import Sale, SaleItem, SaleStatus, PaymentMethod

        if ProductOptionGroup.query.count() == 0:
            milk_group = ProductOptionGroup(name="Milk Selection", is_required=False, display_order=1, is_active=True)
            shot_group = ProductOptionGroup(name="Espresso Shots", is_required=False, display_order=2, is_active=True)
            flavor_group = ProductOptionGroup(name="Syrups & Flavors", is_required=False, display_order=3, is_active=True)
            db.session.add_all([milk_group, shot_group, flavor_group])
            db.session.flush()

            db.session.add_all([
                ProductOption(group_id=milk_group.id, name="Whole Dairy Milk", price_adjustment=Decimal("0.00"), display_order=1, is_available=True),
                ProductOption(group_id=milk_group.id, name="Oat Milk (Barista)", price_adjustment=Decimal("0.85"), display_order=2, is_available=True),
                ProductOption(group_id=shot_group.id, name="Extra Espresso Shot", price_adjustment=Decimal("1.25"), display_order=1, is_available=True),
                ProductOption(group_id=flavor_group.id, name="Vanilla Syrup", price_adjustment=Decimal("0.50"), display_order=1, is_available=True),
                ProductOption(group_id=flavor_group.id, name="Caramel Drizzle", price_adjustment=Decimal("0.60"), display_order=2, is_available=True),
            ])
            db.session.commit()

        # 11. Recipes / Bill of Materials (BOM) (Phase 5)
        if Recipe.query.count() == 0:
            bean_ing = ingredients_map["Specialty Espresso Blend (Beans)"]
            milk_ing = ingredients_map["Whole Dairy Milk"]
            vanilla_ing = ingredients_map["Organic Vanilla Syrup"]
            matcha_ing = ingredients_map["Ceremonial Uji Matcha"]
            cup_ing = ingredients_map["Compostable 12oz Cups"]
            lid_ing = ingredients_map["Eco Sip Lids 12oz"]

            # Double Espresso Recipe
            p_esp = Product.query.filter_by(sku="COF-ESP-001").first()
            if p_esp:
                r_esp = Recipe(product_id=p_esp.id, name="Double Espresso Spec", instructions="Extract 36g espresso from 18g ground coffee in 27-30s.")
                db.session.add(r_esp)
                db.session.flush()
                db.session.add(RecipeItem(recipe_id=r_esp.id, ingredient_id=bean_ing.id, quantity_required=Decimal("18.0000"), unit="g"))

            # Caffe Latte Base Recipe
            p_lat = Product.query.filter_by(sku="COF-LAT-001").first()
            if p_lat:
                r_lat = Recipe(product_id=p_lat.id, name="Caffe Latte 12oz Standard", instructions="Pull double shot into 12oz cup, steam whole milk with microfoam.")
                db.session.add(r_lat)
                db.session.flush()
                db.session.add_all([
                    RecipeItem(recipe_id=r_lat.id, ingredient_id=bean_ing.id, quantity_required=Decimal("18.0000"), unit="g"),
                    RecipeItem(recipe_id=r_lat.id, ingredient_id=milk_ing.id, quantity_required=Decimal("220.0000"), unit="ml"),
                    RecipeItem(recipe_id=r_lat.id, ingredient_id=cup_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                    RecipeItem(recipe_id=r_lat.id, ingredient_id=lid_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                ])

                # Variant Recipe: 16oz Iced Latte
                v_iced = ProductVariant.query.filter_by(sku="COF-LAT-001-16I").first()
                if v_iced:
                    r_iced = Recipe(product_id=p_lat.id, product_variant_id=v_iced.id, name="16oz Iced Caffe Latte", instructions="Fill 16oz cup with ice, pour 260ml cold milk, top with double shot.")
                    db.session.add(r_iced)
                    db.session.flush()
                    db.session.add_all([
                        RecipeItem(recipe_id=r_iced.id, ingredient_id=bean_ing.id, quantity_required=Decimal("20.0000"), unit="g"),
                        RecipeItem(recipe_id=r_iced.id, ingredient_id=milk_ing.id, quantity_required=Decimal("260.0000"), unit="ml"),
                        RecipeItem(recipe_id=r_iced.id, ingredient_id=cup_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                        RecipeItem(recipe_id=r_iced.id, ingredient_id=lid_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                    ])

            # Spanish Latte Recipe
            p_spl = Product.query.filter_by(sku="COF-SPL-001").first()
            if p_spl:
                r_spl = Recipe(product_id=p_spl.id, name="Spanish Latte Standard", instructions="Mix 25ml vanilla syrup with double espresso shot, top with steamed milk.")
                db.session.add(r_spl)
                db.session.flush()
                db.session.add_all([
                    RecipeItem(recipe_id=r_spl.id, ingredient_id=bean_ing.id, quantity_required=Decimal("18.0000"), unit="g"),
                    RecipeItem(recipe_id=r_spl.id, ingredient_id=milk_ing.id, quantity_required=Decimal("200.0000"), unit="ml"),
                    RecipeItem(recipe_id=r_spl.id, ingredient_id=vanilla_ing.id, quantity_required=Decimal("25.0000"), unit="ml"),
                    RecipeItem(recipe_id=r_spl.id, ingredient_id=cup_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                    RecipeItem(recipe_id=r_spl.id, ingredient_id=lid_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                ])

            # Matcha Latte Recipe
            p_mat = Product.query.filter_by(sku="TEA-MAT-001").first()
            if p_mat:
                r_mat = Recipe(product_id=p_mat.id, name="Ceremonial Matcha Latte", instructions="Whisk 5g ceremonial matcha with 40ml 80C water, combine with 200ml steamed milk.")
                db.session.add(r_mat)
                db.session.flush()
                db.session.add_all([
                    RecipeItem(recipe_id=r_mat.id, ingredient_id=matcha_ing.id, quantity_required=Decimal("5.0000"), unit="g"),
                    RecipeItem(recipe_id=r_mat.id, ingredient_id=milk_ing.id, quantity_required=Decimal("200.0000"), unit="ml"),
                    RecipeItem(recipe_id=r_mat.id, ingredient_id=cup_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                    RecipeItem(recipe_id=r_mat.id, ingredient_id=lid_ing.id, quantity_required=Decimal("1.0000"), unit="pcs"),
                ])

            db.session.commit()

        # 12. POS Active Shift for Demo Cashier (Phase 6)
        cashier = users_map[Roles.CASHIER]
        active_shift = POSRegisterShift.query.filter_by(user_id=cashier.id, is_active=True).first()
        if not active_shift:
            demo_shift = POSRegisterShift(
                user_id=cashier.id,
                opening_cash=Decimal("150.00"),
                notes="Morning Counter Shift Float",
                is_active=True
            )
            db.session.add(demo_shift)
            db.session.commit()

        print("[OK] Phase 1 - 6 Database seeding complete! Demo credentials:")
        print("   Username: owner    | Password: OwnerPass123!")
        print("   Username: manager  | Password: ManagerPass123!")
        print("   Username: cashier  | Password: CashierPass123!")
        print("   Username: barista  | Password: BaristaPass123!")
        print("   Username: staff    | Password: StaffPass123!")


if __name__ == "__main__":
    seed()

