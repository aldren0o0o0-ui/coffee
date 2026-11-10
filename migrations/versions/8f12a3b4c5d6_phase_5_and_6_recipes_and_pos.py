"""phase_5_and_6_recipes_and_pos

Revision ID: 8f12a3b4c5d6
Revises: 4cae1a6c9a53
Create Date: 2026-09-17 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8f12a3b4c5d6'
down_revision = '4cae1a6c9a53'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Update 'recipes' table
    op.add_column('recipes', sa.Column('name', sa.String(length=120), nullable=True))
    op.add_column('recipes', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('recipes', sa.Column('product_variant_id', sa.Integer(), nullable=True))
    op.add_column('recipes', sa.Column('prep_notes', sa.Text(), nullable=True))
    op.add_column('recipes', sa.Column('yield_quantity', sa.Numeric(precision=10, scale=2), server_default='1.00', nullable=False))
    op.add_column('recipes', sa.Column('yield_unit', sa.String(length=32), server_default='serving', nullable=False))
    op.add_column('recipes', sa.Column('version', sa.Integer(), server_default='1', nullable=False))

    # Drop old single-column unique constraint on product_id to allow variant recipes
    op.drop_constraint('recipes_product_id_key', 'recipes', type_='unique')

    # Foreign key for product_variant_id
    op.create_foreign_key(
        'recipes_product_variant_id_fkey',
        'recipes', 'product_variants',
        ['product_variant_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index(op.f('ix_recipes_product_variant_id'), 'recipes', ['product_variant_id'], unique=False)

    # 2. Update 'recipe_items' table
    # Convert quantity_required to Numeric(12, 4)
    op.execute("ALTER TABLE recipe_items ALTER COLUMN quantity_required TYPE NUMERIC(12, 4) USING quantity_required::numeric(12, 4)")

    op.add_column('recipe_items', sa.Column('unit', sa.String(length=16), server_default='g', nullable=False))
    op.add_column('recipe_items', sa.Column('unit_of_measure_id', sa.Integer(), nullable=True))
    op.add_column('recipe_items', sa.Column('notes', sa.String(length=255), nullable=True))
    op.add_column('recipe_items', sa.Column('display_order', sa.Integer(), server_default='0', nullable=False))

    op.create_foreign_key(
        'recipe_items_unit_of_measure_id_fkey',
        'recipe_items', 'units_of_measure',
        ['unit_of_measure_id'], ['id'],
        ondelete='SET NULL'
    )

    # 3. Update 'sales' table for idempotency
    op.add_column('sales', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_sales_idempotency_key'), 'sales', ['idempotency_key'], unique=True)

    # 4. Update 'sale_items' table for variants and options
    op.add_column('sale_items', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.add_column('sale_items', sa.Column('variant_name', sa.String(length=80), nullable=True))
    op.add_column('sale_items', sa.Column('options_data', sa.Text(), nullable=True))
    op.add_column('sale_items', sa.Column('options_price', sa.Numeric(precision=10, scale=2), server_default='0.00', nullable=False))

    op.create_foreign_key(
        'sale_items_variant_id_fkey',
        'sale_items', 'product_variants',
        ['variant_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('sale_items_variant_id_fkey', 'sale_items', type_='foreignkey')
    op.drop_column('sale_items', 'options_price')
    op.drop_column('sale_items', 'options_data')
    op.drop_column('sale_items', 'variant_name')
    op.drop_column('sale_items', 'variant_id')

    op.drop_index(op.f('ix_sales_idempotency_key'), table_name='sales')
    op.drop_column('sales', 'idempotency_key')

    op.drop_constraint('recipe_items_unit_of_measure_id_fkey', 'recipe_items', type_='foreignkey')
    op.drop_column('recipe_items', 'display_order')
    op.drop_column('recipe_items', 'notes')
    op.drop_column('recipe_items', 'unit_of_measure_id')
    op.drop_column('recipe_items', 'unit')
    op.execute("ALTER TABLE recipe_items ALTER COLUMN quantity_required TYPE DOUBLE PRECISION USING quantity_required::double precision")

    op.drop_index(op.f('ix_recipes_product_variant_id'), table_name='recipes')
    op.drop_constraint('recipes_product_variant_id_fkey', 'recipes', type_='foreignkey')
    op.create_unique_constraint('recipes_product_id_key', 'recipes', ['product_id'])
    op.drop_column('recipes', 'version')
    op.drop_column('recipes', 'yield_unit')
    op.drop_column('recipes', 'yield_quantity')
    op.drop_column('recipes', 'prep_notes')
    op.drop_column('recipes', 'product_variant_id')
    op.drop_column('recipes', 'description')
    op.drop_column('recipes', 'name')
