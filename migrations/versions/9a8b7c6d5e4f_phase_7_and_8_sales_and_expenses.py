"""phase_7_and_8_sales_and_expenses

Revision ID: 9a8b7c6d5e4f
Revises: 8f12a3b4c5d6
Create Date: 2026-09-18 08:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9a8b7c6d5e4f'
down_revision = '8f12a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create 'payments' table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sale_id', sa.Integer(), sa.ForeignKey('sales.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('payment_method', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('reference_no', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='SUCCESS', nullable=False),
        sa.Column('cash_tendered', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('change_due', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_payments_sale_id'), 'payments', ['sale_id'], unique=False)
    op.create_index(op.f('ix_payments_payment_method'), 'payments', ['payment_method'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_created_at'), 'payments', ['created_at'], unique=False)

    # 2. Update 'sales' table with ledger fields, refund/void tracking, and indexes
    op.add_column('sales', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('sales', sa.Column('payment_status', sa.String(length=32), server_default='PAID', nullable=False))
    op.add_column('sales', sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), server_default='0.00', nullable=False))
    op.add_column('sales', sa.Column('refund_reason', sa.String(length=255), nullable=True))
    op.add_column('sales', sa.Column('refunded_at', sa.DateTime(), nullable=True))
    op.add_column('sales', sa.Column('refunded_by_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('sales', sa.Column('voided_by_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('void_reason', sa.String(length=255), nullable=True))

    op.create_foreign_key('sales_refunded_by_id_fkey', 'sales', 'users', ['refunded_by_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('sales_voided_by_id_fkey', 'sales', 'users', ['voided_by_id'], ['id'], ondelete='SET NULL')

    op.create_index(op.f('ix_sales_created_at'), 'sales', ['created_at'], unique=False)
    op.create_index(op.f('ix_sales_status'), 'sales', ['status'], unique=False)
    op.create_index(op.f('ix_sales_payment_method'), 'sales', ['payment_method'], unique=False)
    op.create_index(op.f('ix_sales_user_id'), 'sales', ['user_id'], unique=False)
    op.create_index(op.f('ix_sales_shift_id'), 'sales', ['shift_id'], unique=False)

    # Backfill payments for existing sales if any exist
    op.execute("""
        INSERT INTO payments (sale_id, payment_method, amount, status, cash_tendered, change_due, created_by_id, created_at)
        SELECT id, payment_method, total_amount, 'SUCCESS', cash_tendered, change_due, user_id, created_at
        FROM sales
        WHERE id NOT IN (SELECT sale_id FROM payments);
    """)

    # 3. Update 'expense_categories' table
    op.add_column('expense_categories', sa.Column('code', sa.String(length=32), nullable=True))
    op.add_column('expense_categories', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('expense_categories', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('expense_categories', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))

    # Backfill codes for existing categories
    op.execute("""
        UPDATE expense_categories
        SET code = UPPER(SUBSTRING(REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '', 'g'), 1, 6)) || '_' || id
        WHERE code IS NULL;
    """)
    op.alter_column('expense_categories', 'code', nullable=False)
    op.create_index(op.f('ix_expense_categories_code'), 'expense_categories', ['code'], unique=True)

    # 4. Update 'expenses' table
    op.add_column('expenses', sa.Column('expense_number', sa.String(length=32), nullable=True))
    op.add_column('expenses', sa.Column('payment_method', sa.String(length=32), server_default='Cash', nullable=False))
    op.add_column('expenses', sa.Column('vendor_payee', sa.String(length=120), nullable=True))
    op.add_column('expenses', sa.Column('status', sa.String(length=32), server_default='RECORDED', nullable=False))
    op.add_column('expenses', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('expenses', sa.Column('voided_by_id', sa.Integer(), nullable=True))
    op.add_column('expenses', sa.Column('void_reason', sa.String(length=255), nullable=True))
    op.add_column('expenses', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))

    op.create_foreign_key('expenses_voided_by_id_fkey', 'expenses', 'users', ['voided_by_id'], ['id'], ondelete='SET NULL')

    # Backfill expense_number for existing expenses
    op.execute("""
        UPDATE expenses
        SET expense_number = 'EXP-' || TO_CHAR(expense_date, 'YYYYMMDD') || '-' || LPAD(id::text, 4, '0')
        WHERE expense_number IS NULL;
    """)
    op.alter_column('expenses', 'expense_number', nullable=False)
    op.create_index(op.f('ix_expenses_expense_number'), 'expenses', ['expense_number'], unique=True)
    op.create_index(op.f('ix_expenses_status'), 'expenses', ['status'], unique=False)
    op.create_index(op.f('ix_expenses_expense_date'), 'expenses', ['expense_date'], unique=False)
    op.create_index('ix_expenses_date_cat_status', 'expenses', ['expense_date', 'category_id', 'status'], unique=False)

    # Check constraint on amount > 0
    op.create_check_constraint('ck_expenses_amount_positive', 'expenses', 'amount > 0')


def downgrade():
    op.drop_constraint('ck_expenses_amount_positive', 'expenses', type_='check')
    op.drop_index('ix_expenses_date_cat_status', table_name='expenses')
    op.drop_index(op.f('ix_expenses_expense_date'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_status'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_expense_number'), table_name='expenses')
    op.drop_constraint('expenses_voided_by_id_fkey', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'updated_at')
    op.drop_column('expenses', 'void_reason')
    op.drop_column('expenses', 'voided_by_id')
    op.drop_column('expenses', 'voided_at')
    op.drop_column('expenses', 'status')
    op.drop_column('expenses', 'vendor_payee')
    op.drop_column('expenses', 'payment_method')
    op.drop_column('expenses', 'expense_number')

    op.drop_index(op.f('ix_expense_categories_code'), table_name='expense_categories')
    op.drop_column('expense_categories', 'updated_at')
    op.drop_column('expense_categories', 'created_at')
    op.drop_column('expense_categories', 'is_active')
    op.drop_column('expense_categories', 'code')

    op.drop_index(op.f('ix_sales_shift_id'), table_name='sales')
    op.drop_index(op.f('ix_sales_user_id'), table_name='sales')
    op.drop_index(op.f('ix_sales_payment_method'), table_name='sales')
    op.drop_index(op.f('ix_sales_status'), table_name='sales')
    op.drop_index(op.f('ix_sales_created_at'), table_name='sales')
    op.drop_constraint('sales_voided_by_id_fkey', 'sales', type_='foreignkey')
    op.drop_constraint('sales_refunded_by_id_fkey', 'sales', type_='foreignkey')
    op.drop_column('sales', 'void_reason')
    op.drop_column('sales', 'voided_by_id')
    op.drop_column('sales', 'voided_at')
    op.drop_column('sales', 'refunded_by_id')
    op.drop_column('sales', 'refunded_at')
    op.drop_column('sales', 'refund_reason')
    op.drop_column('sales', 'refund_amount')
    op.drop_column('sales', 'payment_status')
    op.drop_column('sales', 'updated_at')

    op.drop_index(op.f('ix_payments_created_at'), table_name='payments')
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_payment_method'), table_name='payments')
    op.drop_index(op.f('ix_payments_sale_id'), table_name='payments')
    op.drop_table('payments')
