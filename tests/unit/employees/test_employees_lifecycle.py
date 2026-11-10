import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from app.extensions import db
from app.modules.users.models import User
from app.modules.employees.models import (
    EmployeeProfile,
    EmployeeSchedule,
    ShiftAttendance,
    EmploymentStatus,
    ScheduleStatus,
    AttendanceStatus,
)
from app.modules.employees.services import EmployeeService
from app.modules.auth.models import AuditLog
from app.core.exceptions import ValidationError, NotFoundError


def test_employee_profile_creation_and_update(app, staff_user):
    """Test automatic profile creation, code generation, and updates."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    assert profile is not None
    assert profile.user_id == staff_user.id
    assert profile.employee_code.startswith("EMP-")
    assert profile.employment_status == EmploymentStatus.ACTIVE
    assert profile.hourly_rate == Decimal("15.00")

    # Update profile
    updated = EmployeeService.update_profile(
        staff_user.id,
        phone="+1-555-0199",
        hourly_rate=18.50,
        position="Senior Barista",
        address="123 Coffee Way",
        emergency_contact="Jane Doe",
        emergency_contact_phone="+1-555-0100",
        notes="Keyholder",
    )
    assert updated.phone == "+1-555-0199"
    assert updated.hourly_rate == Decimal("18.50")
    assert updated.position == "Senior Barista"
    assert updated.address == "123 Coffee Way"
    assert updated.notes == "Keyholder"
    assert updated.full_name == staff_user.full_name


def test_employee_schedule_creation_and_conflict_detection(app, staff_user, manager_user):
    """Test creating shift schedule and preventing overlapping assignments."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    work_day = date.today() + timedelta(days=1)

    # 1. Create initial shift 08:00 - 12:00
    sched1 = EmployeeService.create_schedule(
        employee_id=profile.id,
        work_date=work_day,
        start_time=time(8, 0),
        end_time=time(12, 0),
        notes="Morning Shift",
        created_by_id=manager_user.id,
    )
    assert sched1.id is not None
    assert sched1.scheduled_hours == 4.0
    assert sched1.status == ScheduleStatus.SCHEDULED

    # 2. Attempt overlapping shift: 10:00 - 14:00 (overlaps with 08:00 - 12:00)
    with pytest.raises(ValidationError) as exc:
        EmployeeService.create_schedule(
            employee_id=profile.id,
            work_date=work_day,
            start_time=time(10, 0),
            end_time=time(14, 0),
            created_by_id=manager_user.id,
        )
    assert "conflicts with an existing shift" in str(exc.value)

    # 3. Create non-overlapping evening shift on same day: 13:00 - 17:00 (allowed)
    sched2 = EmployeeService.create_schedule(
        employee_id=profile.id,
        work_date=work_day,
        start_time=time(13, 0),
        end_time=time(17, 0),
        notes="Afternoon Shift",
        created_by_id=manager_user.id,
    )
    assert sched2.id is not None
    assert sched2.scheduled_hours == 4.0

    # 4. Cancel a schedule
    cancelled = EmployeeService.cancel_schedule(sched1.id, updated_by_id=manager_user.id)
    assert cancelled.status == ScheduleStatus.CANCELLED

    # 5. Now the morning time slot can be re-scheduled since sched1 was cancelled
    sched3 = EmployeeService.create_schedule(
        employee_id=profile.id,
        work_date=work_day,
        start_time=time(8, 0),
        end_time=time(12, 0),
        notes="Replacement Morning Shift",
        created_by_id=manager_user.id,
    )
    assert sched3.id is not None


def test_clock_in_clock_out_and_breaks(app, staff_user):
    """Test full attendance flow: clock in, break start/end, and clock out."""
    # 1. Clock in
    att = EmployeeService.clock_in(staff_user.id, notes="On time")
    assert att.id is not None
    assert att.clock_in is not None
    assert att.clock_out is None
    assert att.is_active is True
    assert att.is_on_break is False

    # 2. Attempt double clock-in (must fail)
    with pytest.raises(ValidationError) as exc:
        EmployeeService.clock_in(staff_user.id)
    assert "already have an active shift" in str(exc.value)

    # 3. Start break
    EmployeeService.start_break(staff_user.id)
    assert att.is_on_break is True
    assert att.break_start_at is not None

    # 4. Attempt clock-out during active break (must fail)
    with pytest.raises(ValidationError) as exc:
        EmployeeService.clock_out(staff_user.id)
    assert "currently on break" in str(exc.value)

    # 5. End break
    EmployeeService.end_break(staff_user.id)
    assert att.is_on_break is False
    assert att.break_end_at is not None

    # 6. Clock out
    closed_att = EmployeeService.clock_out(staff_user.id, notes="Smooth shift")
    assert closed_att.clock_out is not None
    assert closed_att.is_active is False
    assert closed_att.worked_minutes >= 0

    # 7. Attempt clock out again with no active shift (must fail)
    with pytest.raises(ValidationError) as exc:
        EmployeeService.clock_out(staff_user.id)
    assert "no active shift" in str(exc.value)


def test_late_minutes_and_schedule_linkage(app, staff_user):
    """Test calculation of late minutes when clock-in is past scheduled start + grace period."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    today = date.today()

    # Schedule: 08:00 start
    sched = EmployeeService.create_schedule(
        employee_id=profile.id,
        work_date=today,
        start_time=time(8, 0),
        end_time=time(16, 0),
    )

    # Create an attendance with clock_in at 08:25 (25 minutes late, > 5m grace period)
    att = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        schedule_id=sched.id,
        attendance_date=today,
        scheduled_start=time(8, 0),
        scheduled_end=time(16, 0),
        clock_in=datetime.combine(today, time(8, 25)),
    )
    att.calculate_metrics()
    db.session.add(att)
    db.session.commit()

    assert att.late_minutes == 25
    assert att.status == AttendanceStatus.LATE


def test_manager_attendance_correction_with_audit(app, staff_user, manager_user):
    """Test manager manual correction of an attendance record and verify audit trail."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    today = date.today()

    att = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        attendance_date=today,
        clock_in=datetime.combine(today, time(9, 0)),
        clock_out=datetime.combine(today, time(13, 0)),
        total_hours=4.0,
        worked_minutes=240,
        status=AttendanceStatus.PRESENT,
    )
    db.session.add(att)
    db.session.commit()

    # Manager corrects hours because staff forgot to clock in at 08:00
    new_in = datetime.combine(today, time(8, 0))
    new_out = datetime.combine(today, time(13, 0))
    reason = "Staff was on duty since 08:00 helping with morning espresso bar prep"

    corrected = EmployeeService.correct_attendance(
        attendance_id=att.id,
        clock_in=new_in,
        clock_out=new_out,
        status=AttendanceStatus.CORRECTED,
        reason=reason,
        manager_id=manager_user.id,
    )

    assert corrected.total_hours == 5.0
    assert corrected.worked_minutes == 300
    assert corrected.status == AttendanceStatus.CORRECTED
    assert corrected.corrected_by_id == manager_user.id
    assert corrected.correction_reason == reason

    # Check audit log entry
    audit = AuditLog.query.filter_by(action="ATTENDANCE_CORRECTED", user_id=manager_user.id).first()
    assert audit is not None
    assert reason in audit.details


def test_attendance_summary_and_labor_cost(app, staff_user):
    """Test attendance KPI aggregation and estimated labor cost calculation."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    profile.hourly_rate = Decimal("20.00")
    db.session.commit()

    today = date.today()

    # Create 2 attendance records: 4 hours and 6 hours = 10 hours total
    att1 = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        attendance_date=today,
        clock_in=datetime.combine(today, time(8, 0)),
        clock_out=datetime.combine(today, time(12, 0)),
        total_hours=4.0,
        worked_minutes=240,
        status=AttendanceStatus.PRESENT,
    )
    att2 = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        attendance_date=today,
        clock_in=datetime.combine(today, time(13, 0)),
        clock_out=datetime.combine(today, time(19, 0)),
        total_hours=6.0,
        worked_minutes=360,
        late_minutes=15,
        status=AttendanceStatus.LATE,
    )
    db.session.add_all([att1, att2])
    db.session.commit()

    summary = EmployeeService.get_attendance_summary(start_date=today, end_date=today)
    assert summary["total_shifts"] == 2
    assert summary["total_hours"] == 10.0
    assert summary["late_count"] == 1
    # Labor cost = 10 hours * $20.00 = $200.00
    assert summary["total_labor_cost"] == Decimal("200.00")
