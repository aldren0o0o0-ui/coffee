from datetime import datetime, time
from app.core.exceptions import ValidationError
from app.modules.employees.models import ShiftAttendance, EmployeeSchedule, ScheduleStatus


def validate_can_clock_in(user_id):
    """Validate that the user does not already have an active shift."""
    active = ShiftAttendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if active:
        raise ValidationError("You already have an active shift clocked in.")
    return True


def validate_can_clock_out(user_id):
    """Validate that the user has an active shift and is not currently paused on break."""
    active = ShiftAttendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if not active:
        raise ValidationError("You have no active shift to clock out from.")
    if active.is_on_break:
        raise ValidationError("You are currently on break. Please end your break before clocking out.")
    return active


def validate_can_start_break(user_id):
    """Validate that the user can start a break."""
    active = ShiftAttendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if not active:
        raise ValidationError("You have no active shift to start a break for.")
    if active.is_on_break:
        raise ValidationError("You are already on break.")
    return active


def validate_can_end_break(user_id):
    """Validate that the user is currently on break."""
    active = ShiftAttendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if not active:
        raise ValidationError("You have no active shift.")
    if not active.is_on_break:
        raise ValidationError("You are not currently on break.")
    return active


def validate_schedule(employee_id, work_date, start_time, end_time, schedule_id=None):
    """
    Validate schedule parameters and check for overlapping shifts for the same employee.
    """
    if not employee_id:
        raise ValidationError("Employee profile is required.")
    if not work_date:
        raise ValidationError("Work date is required.")
    if not start_time or not end_time:
        raise ValidationError("Both start time and end time are required.")

    # Calculate minute representations
    start_min = start_time.hour * 60 + start_time.minute
    end_min = end_time.hour * 60 + end_time.minute

    if start_min == end_min:
        raise ValidationError("Shift start time and end time cannot be identical.")

    # Query for existing non-cancelled shifts on the same date
    query = EmployeeSchedule.query.filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.work_date == work_date,
        EmployeeSchedule.status != ScheduleStatus.CANCELLED
    )
    if schedule_id:
        query = query.filter(EmployeeSchedule.id != schedule_id)

    existing_schedules = query.all()
    for ex in existing_schedules:
        ex_start = ex.start_time.hour * 60 + ex.start_time.minute
        ex_end = ex.end_time.hour * 60 + ex.end_time.minute

        # Check standard same-day overlap
        # Overlap occurs when start_min < ex_end and end_min > ex_start
        if start_min < ex_end and end_min > ex_start:
            raise ValidationError(
                f"Schedule conflicts with an existing shift ({ex.start_time.strftime('%I:%M %p')} - {ex.end_time.strftime('%I:%M %p')}) on {work_date}."
            )

    return True


def validate_attendance_correction(clock_in, clock_out, reason):
    """Validate manual manager correction parameters."""
    if not clock_in:
        raise ValidationError("Clock-in timestamp is required.")
    if clock_out and clock_out <= clock_in:
        raise ValidationError("Clock-out timestamp must be after clock-in timestamp.")
    if not reason or not reason.strip():
        raise ValidationError("A clear justification/reason is required for attendance corrections.")
    return True
