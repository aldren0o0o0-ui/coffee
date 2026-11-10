"""phase_3_and_4_catalog_and_inventory

Revision ID: 4cae1a6c9a53
Revises: d84bd4cb01aa
Create Date: 2026-09-17 22:51:24.538356

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4cae1a6c9a53'
down_revision = 'd84bd4cb01aa'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create units_of_measure table
    op.create_table(
        'units_of_measure',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_units_of_measure_code'), 'units_of_measure', ['code'], unique=True)

    # 2. Create inventory_categories table
    op.create_table(
        'inventory_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_inventory_categories_code'), 'inventory_categories', ['code'], unique=True)

    # 3. Create product_option_groups & product_options & associations
    op.create_table(
        'product_option_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, default=False),
        sa.Column('max_select', sa.Integer(), nullable=False, default=1),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'product_options',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('product_option_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('price_adjustment', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('is_available', sa.Boolean(), nullable=False, default=True),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
    )
    op.create_index(op.f('ix_product_options_group_id'), 'product_options', ['group_id'], unique=False)

    op.create_table(
        'product_option_group_associations',
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('option_group_id', sa.Integer(), sa.ForeignKey('product_option_groups.id', ondelete='CASCADE'), primary_key=True),
    )

    # 4. Create product_variants table
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('sku', sa.String(length=32), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('is_available', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('price >= 0', name='ck_variant_price_non_negative'),
        sa.CheckConstraint('cost_price >= 0', name='ck_variant_cost_price_non_negative'),
        sa.CheckConstraint('display_order >= 0', name='ck_variant_display_order_non_negative'),
    )
    op.create_index(op.f('ix_product_variants_product_id'), 'product_variants', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_variants_sku'), 'product_variants', ['sku'], unique=True)
    op.create_index(op.f('ix_product_variants_is_available'), 'product_variants', ['is_available'], unique=False)
    op.create_index(op.f('ix_product_variants_is_active'), 'product_variants', ['is_active'], unique=False)

    # 5. Create purchases & purchase_items
    op.create_table(
        'purchases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('suppliers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reference_number', sa.String(length=64), nullable=False),
        sa.Column('purchase_date', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('total_cost', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_purchases_supplier_id'), 'purchases', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_purchases_reference_number'), 'purchases', ['reference_number'], unique=True)
    op.create_index(op.f('ix_purchases_status'), 'purchases', ['status'], unique=False)

    op.create_table(
        'purchase_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('purchase_id', sa.Integer(), sa.ForeignKey('purchases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), sa.ForeignKey('ingredients.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
    )
    op.create_index(op.f('ix_purchase_items_purchase_id'), 'purchase_items', ['purchase_id'], unique=False)
    op.create_index(op.f('ix_purchase_items_ingredient_id'), 'purchase_items', ['ingredient_id'], unique=False)

    # 6. Update categories table (add slug, created_at, updated_at safely)
    op.add_column('categories', sa.Column('slug', sa.String(length=64), nullable=True))
    op.add_column('categories', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.add_column('categories', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    # Backfill slug from name
    op.execute("UPDATE categories SET slug = LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]+', '-', 'g')) WHERE slug IS NULL")
    op.alter_column('categories', 'slug', nullable=False)
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.create_index(op.f('ix_categories_is_active'), 'categories', ['is_active'], unique=False)
    op.execute("ALTER TABLE categories ADD CONSTRAINT ck_category_display_order_non_negative CHECK (display_order >= 0)")

    # 7. Update products table (add slug, is_active, display_order safely)
    op.add_column('products', sa.Column('slug', sa.String(length=120), nullable=True))
    op.add_column('products', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('products', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))
    # Backfill slug from name + id
    op.execute("UPDATE products SET slug = LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]+', '-', 'g')) || '-' || id WHERE slug IS NULL")
    op.alter_column('products', 'slug', nullable=False)
    op.create_index(op.f('ix_products_slug'), 'products', ['slug'], unique=False)
    op.create_index(op.f('ix_products_is_active'), 'products', ['is_active'], unique=False)
    op.create_index(op.f('ix_products_is_available'), 'products', ['is_available'], unique=False)
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
    op.execute("ALTER TABLE products ADD CONSTRAINT ck_product_base_price_non_negative CHECK (base_price >= 0)")
    op.execute("ALTER TABLE products ADD CONSTRAINT ck_product_cost_price_non_negative CHECK (cost_price >= 0)")
    op.execute("ALTER TABLE products ADD CONSTRAINT ck_product_display_order_non_negative CHECK (display_order >= 0)")

    # 8. Update suppliers table
    op.add_column('suppliers', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('suppliers', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # 9. Update ingredients table
    op.add_column('ingredients', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('ingredients', sa.Column('category_id', sa.Integer(), sa.ForeignKey('inventory_categories.id', ondelete='SET NULL'), nullable=True))
    op.add_column('ingredients', sa.Column('unit_of_measure_id', sa.Integer(), sa.ForeignKey('units_of_measure.id', ondelete='RESTRICT'), nullable=True))
    op.add_column('ingredients', sa.Column('current_quantity', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0.0000'))
    op.add_column('ingredients', sa.Column('minimum_stock_level', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0.0000'))
    op.add_column('ingredients', sa.Column('reorder_level', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0.0000'))
    op.add_column('ingredients', sa.Column('maximum_stock_level', sa.Numeric(precision=12, scale=4), nullable=True))
    op.add_column('ingredients', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Backfill current_quantity and minimum_stock_level from legacy columns if they exist
    op.execute("UPDATE ingredients SET current_quantity = current_stock::numeric, minimum_stock_level = minimum_stock::numeric, reorder_level = minimum_stock::numeric")
    op.drop_column('ingredients', 'current_stock')
    op.drop_column('ingredients', 'minimum_stock')

    op.create_index(op.f('ix_ingredients_category_id'), 'ingredients', ['category_id'], unique=False)
    op.create_index(op.f('ix_ingredients_unit_of_measure_id'), 'ingredients', ['unit_of_measure_id'], unique=False)
    op.create_index(op.f('ix_ingredients_is_active'), 'ingredients', ['is_active'], unique=False)
    op.create_index(op.f('ix_ingredients_supplier_id'), 'ingredients', ['supplier_id'], unique=False)
    op.execute("ALTER TABLE ingredients ADD CONSTRAINT ck_ingredient_current_quantity_non_negative CHECK (current_quantity >= 0)")
    op.execute("ALTER TABLE ingredients ADD CONSTRAINT ck_ingredient_min_stock_non_negative CHECK (minimum_stock_level >= 0)")
    op.execute("ALTER TABLE ingredients ADD CONSTRAINT ck_ingredient_reorder_level_non_negative CHECK (reorder_level >= 0)")
    op.execute("ALTER TABLE ingredients ADD CONSTRAINT ck_ingredient_cost_per_unit_non_negative CHECK (cost_per_unit >= 0)")

    # 10. Update stock_movements table
    op.add_column('stock_movements', sa.Column('reference_type', sa.String(length=32), nullable=True))
    op.add_column('stock_movements', sa.Column('reference_id', sa.Integer(), nullable=True))
    op.add_column('stock_movements', sa.Column('reason', sa.String(length=255), nullable=True))
    op.alter_column('stock_movements', 'quantity', existing_type=sa.Float(), type_=sa.Numeric(precision=12, scale=4), postgresql_using='quantity::numeric')
    op.alter_column('stock_movements', 'notes', existing_type=sa.String(length=255), type_=sa.Text())
    op.create_index(op.f('ix_stock_movements_movement_type'), 'stock_movements', ['movement_type'], unique=False)
    op.create_index(op.f('ix_stock_movements_ingredient_id'), 'stock_movements', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_created_at'), 'stock_movements', ['created_at'], unique=False)

    # 11. Seed baseline units of measure and inventory categories
    op.execute("""
        INSERT INTO units_of_measure (code, name, category, is_active, created_at)
        VALUES 
            ('KG', 'Kilogram', 'WEIGHT', true, NOW()),
            ('G', 'Gram', 'WEIGHT', true, NOW()),
            ('L', 'Liter', 'VOLUME', true, NOW()),
            ('ML', 'Milliliter', 'VOLUME', true, NOW()),
            ('PCS', 'Pieces', 'COUNT', true, NOW()),
            ('PACK', 'Pack', 'PACKAGING', true, NOW()),
            ('BOX', 'Box', 'PACKAGING', true, NOW()),
            ('BOTTLE', 'Bottle', 'PACKAGING', true, NOW())
        ON CONFLICT (code) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO inventory_categories (name, code, description, is_active, display_order, created_at)
        VALUES 
            ('Coffee Beans', 'BEANS', 'Whole bean and roasted coffee', true, 1, NOW()),
            ('Milk & Dairy', 'DAIRY', 'Fresh milk, plant-based milk and cream', true, 2, NOW()),
            ('Syrups & Flavoring', 'SYRUPS', 'Flavored beverage syrups and sauces', true, 3, NOW()),
            ('Tea & Powders', 'TEA', 'Loose tea, matcha and chocolate powders', true, 4, NOW()),
            ('Sweeteners', 'SWEET', 'Sugar, honey and sweeteners', true, 5, NOW()),
            ('Packaging & Disposables', 'PACK', 'Cups, lids, straws and takeout bags', true, 6, NOW()),
            ('Cleaning & Consumables', 'CLEAN', 'Filter papers and cleaning chemicals', true, 7, NOW())
        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade():
    op.drop_table('purchase_items')
    op.drop_table('purchases')
    op.drop_table('product_variants')
    op.drop_table('product_option_group_associations')
    op.drop_table('product_options')
    op.drop_table('product_option_groups')
    op.drop_table('inventory_categories')
    op.drop_table('units_of_measure')
