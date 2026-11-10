"""phase_9_and_10_staff_and_reporting

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-09-18 09:42:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Update 'employee_profiles' table
    op.add_column('employee_profiles', sa.Column('employee_code', sa.String(length=32), nullable=True))
    op.add_column('employee_profiles', sa.Column('position', sa.String(length=64), server_default='Staff', nullable=False))
    op.add_column('employee_profiles', sa.Column('employment_status', sa.String(length=32), server_default='ACTIVE', nullable=False))
    op.add_column('employee_profiles', sa.Column('address', sa.String(length=255), nullable=True))
    op.add_column('employee_profiles', sa.Column('emergency_contact_phone', sa.String(length=32), nullable=True))
    op.add_column('employee_profiles', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('employee_profiles', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('employee_profiles', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))

    # Backfill employee_code for existing profiles
    op.execute("""
        UPDATE employee_profiles
        SET employee_code = 'EMP-' || LPAD(id::text, 4, '0')
        WHERE employee_code IS NULL;
    """)
    op.alter_column('employee_profiles', 'employee_code', nullable=False)
    op.create_index(op.f('ix_employee_profiles_employee_code'), 'employee_profiles', ['employee_code'], unique=True)
    op.create_index(op.f('ix_employee_profiles_employment_status'), 'employee_profiles', ['employment_status'], unique=False)

    # 2. Create 'employee_schedules' table
    op.create_table(
        'employee_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employee_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_start', sa.Time(), nullable=True),
        sa.Column('break_end', sa.Time(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='SCHEDULED', nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_employee_schedules_employee_id'), 'employee_schedules', ['employee_id'], unique=False)
    op.create_index(op.f('ix_employee_schedules_work_date'), 'employee_schedules', ['work_date'], unique=False)
    op.create_index(op.f('ix_employee_schedules_status'), 'employee_schedules', ['status'], unique=False)
    op.create_index('ix_employee_schedules_emp_date', 'employee_schedules', ['employee_id', 'work_date'], unique=False)

    # 3. Update 'shift_attendances' table
    op.add_column('shift_attendances', sa.Column('employee_id', sa.Integer(), nullable=True))
    op.add_column('shift_attendances', sa.Column('schedule_id', sa.Integer(), nullable=True))
    op.add_column('shift_attendances', sa.Column('attendance_date', sa.Date(), nullable=True))
    op.add_column('shift_attendances', sa.Column('scheduled_start', sa.Time(), nullable=True))
    op.add_column('shift_attendances', sa.Column('scheduled_end', sa.Time(), nullable=True))
    op.add_column('shift_attendances', sa.Column('break_start_at', sa.DateTime(), nullable=True))
    op.add_column('shift_attendances', sa.Column('break_end_at', sa.DateTime(), nullable=True))
    op.add_column('shift_attendances', sa.Column('status', sa.String(length=32), server_default='PRESENT', nullable=False))
    op.add_column('shift_attendances', sa.Column('late_minutes', sa.Integer(), server_default='0', nullable=False))
    op.add_column('shift_attendances', sa.Column('undertime_minutes', sa.Integer(), server_default='0', nullable=False))
    op.add_column('shift_attendances', sa.Column('worked_minutes', sa.Integer(), server_default='0', nullable=False))
    op.add_column('shift_attendances', sa.Column('corrected_by_id', sa.Integer(), nullable=True))
    op.add_column('shift_attendances', sa.Column('correction_reason', sa.String(length=255), nullable=True))
    op.add_column('shift_attendances', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('shift_attendances', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))

    op.create_foreign_key('shift_attendances_employee_id_fkey', 'shift_attendances', 'employee_profiles', ['employee_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('shift_attendances_schedule_id_fkey', 'shift_attendances', 'employee_schedules', ['schedule_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('shift_attendances_corrected_by_id_fkey', 'shift_attendances', 'users', ['corrected_by_id'], ['id'], ondelete='SET NULL')

    # Backfill attendance_date and employee_id for existing rows
    op.execute("""
        UPDATE shift_attendances
        SET attendance_date = clock_in::date
        WHERE attendance_date IS NULL;
    """)
    op.execute("""
        UPDATE shift_attendances sa
        SET employee_id = ep.id
        FROM employee_profiles ep
        WHERE sa.user_id = ep.user_id AND sa.employee_id IS NULL;
    """)

    op.create_index(op.f('ix_shift_attendances_employee_id'), 'shift_attendances', ['employee_id'], unique=False)
    op.create_index(op.f('ix_shift_attendances_schedule_id'), 'shift_attendances', ['schedule_id'], unique=False)
    op.create_index(op.f('ix_shift_attendances_attendance_date'), 'shift_attendances', ['attendance_date'], unique=False)
    op.create_index(op.f('ix_shift_attendances_status'), 'shift_attendances', ['status'], unique=False)

    # 4. Performance indexes for Phase 10 Reporting
    op.create_index('ix_sales_created_status', 'sales', ['created_at', 'status'], unique=False)
    op.create_index('ix_sale_items_sale_prod', 'sale_items', ['sale_id', 'product_id'], unique=False)


def downgrade():
    op.drop_index('ix_sale_items_sale_prod', table_name='sale_items')
    op.drop_index('ix_sales_created_status', table_name='sales')

    op.drop_index(op.f('ix_shift_attendances_status'), table_name='shift_attendances')
    op.drop_index(op.f('ix_shift_attendances_attendance_date'), table_name='shift_attendances')
    op.drop_index(op.f('ix_shift_attendances_schedule_id'), table_name='shift_attendances')
    op.drop_index(op.f('ix_shift_attendances_employee_id'), table_name='shift_attendances')
    op.drop_constraint('shift_attendances_corrected_by_id_fkey', 'shift_attendances', type_='foreignkey')
    op.drop_constraint('shift_attendances_schedule_id_fkey', 'shift_attendances', type_='foreignkey')
    op.drop_constraint('shift_attendances_employee_id_fkey', 'shift_attendances', type_='foreignkey')
    op.drop_column('shift_attendances', 'updated_at')
    op.drop_column('shift_attendances', 'created_at')
    op.drop_column('shift_attendances', 'correction_reason')
    op.drop_column('shift_attendances', 'corrected_by_id')
    op.drop_column('shift_attendances', 'worked_minutes')
    op.drop_column('shift_attendances', 'undertime_minutes')
    op.drop_column('shift_attendances', 'late_minutes')
    op.drop_column('shift_attendances', 'status')
    op.drop_column('shift_attendances', 'break_end_at')
    op.drop_column('shift_attendances', 'break_start_at')
    op.drop_column('shift_attendances', 'scheduled_end')
    op.drop_column('shift_attendances', 'scheduled_start')
    op.drop_column('shift_attendances', 'attendance_date')
    op.drop_column('shift_attendances', 'schedule_id')
    op.drop_column('shift_attendances', 'employee_id')

    op.drop_index('ix_employee_schedules_emp_date', table_name='employee_schedules')
    op.drop_index(op.f('ix_employee_schedules_status'), table_name='employee_schedules')
    op.drop_index(op.f('ix_employee_schedules_work_date'), table_name='employee_schedules')
    op.drop_index(op.f('ix_employee_schedules_employee_id'), table_name='employee_schedules')
    op.drop_table('employee_schedules')

    op.drop_index(op.f('ix_employee_profiles_employment_status'), table_name='employee_profiles')
    op.drop_index(op.f('ix_employee_profiles_employee_code'), table_name='employee_profiles')
    op.drop_column('employee_profiles', 'updated_at')
    op.drop_column('employee_profiles', 'created_at')
    op.drop_column('employee_profiles', 'notes')
    op.drop_column('employee_profiles', 'emergency_contact_phone')
    op.drop_column('employee_profiles', 'address')
    op.drop_column('employee_profiles', 'employment_status')
    op.drop_column('employee_profiles', 'position')
    op.drop_column('employee_profiles', 'employee_code')
