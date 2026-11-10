from datetime import datetime, date, time, timedelta
from decimal import Decimal
from sqlalchemy import func, or_
from app.extensions import db
from app.modules.employees.models import (
    EmployeeProfile,
    EmployeeSchedule,
    ShiftAttendance,
    EmploymentStatus,
    ScheduleStatus,
    AttendanceStatus,
)
from app.modules.employees.validators import (
    validate_can_clock_in,
    validate_can_clock_out,
    validate_can_start_break,
    validate_can_end_break,
    validate_schedule,
    validate_attendance_correction,
)
from app.modules.auth.models import AuditLog
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_query
from app.core.utilities import generate_employee_code


class EmployeeService:
    # -------------------------------------------------------------
    # Employee Profile Methods
    # -------------------------------------------------------------

    @staticmethod
    def get_or_create_profile(user_id):
        """Retrieve existing employee profile or create default profile if missing."""
        profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            code = generate_employee_code(user_id)
            # Ensure code is unique in rare edge cases
            existing_code = EmployeeProfile.query.filter_by(employee_code=code).first()
            if existing_code:
                code = f"EMP-{user_id:04d}-{date.today().year}"

            profile = EmployeeProfile(
                user_id=user_id,
                employee_code=code,
                position="Staff",
                employment_status=EmploymentStatus.ACTIVE,
                hourly_rate=Decimal("15.00"),
                hire_date=date.today(),
            )
            db.session.add(profile)
            db.session.commit()
        return profile

    @staticmethod
    def get_profile_by_id(profile_id):
        profile = db.session.get(EmployeeProfile, profile_id)
        if not profile:
            raise NotFoundError(f"Employee profile #{profile_id} not found.")
        return profile

    @staticmethod
    def get_profile_by_user_id(user_id):
        profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return EmployeeService.get_or_create_profile(user_id)
        return profile

    @staticmethod
    def get_all_profiles(active_only=False):
        query = EmployeeProfile.query
        if active_only:
            query = query.filter(EmployeeProfile.employment_status == EmploymentStatus.ACTIVE)
        return query.order_by(EmployeeProfile.id.asc()).all()

    @staticmethod
    def update_profile(
        user_id,
        phone=None,
        hourly_rate=None,
        hire_date=None,
        emergency_contact=None,
        position=None,
        employment_status=None,
        address=None,
        emergency_contact_phone=None,
        notes=None,
    ):
        profile = EmployeeService.get_or_create_profile(user_id)
        if phone is not None:
            profile.phone = phone.strip() if phone else None
        if hourly_rate is not None:
            profile.hourly_rate = Decimal(str(hourly_rate))
        if hire_date is not None:
            profile.hire_date = hire_date
        if emergency_contact is not None:
            profile.emergency_contact = emergency_contact.strip() if emergency_contact else None
        if position is not None:
            profile.position = position.strip() or "Staff"
        if employment_status is not None:
            if employment_status in EmploymentStatus.ALL:
                profile.employment_status = employment_status
        if address is not None:
            profile.address = address.strip() if address else None
        if emergency_contact_phone is not None:
            profile.emergency_contact_phone = emergency_contact_phone.strip() if emergency_contact_phone else None
        if notes is not None:
            profile.notes = notes.strip() if notes else None

        profile.updated_at = datetime.utcnow()
        db.session.commit()
        return profile

    # -------------------------------------------------------------
    # Shift Scheduling Methods
    # -------------------------------------------------------------

    @staticmethod
    def create_schedule(
        employee_id,
        work_date,
        start_time,
        end_time,
        break_start=None,
        break_end=None,
        notes="",
        created_by_id=None,
    ):
        """Create and validate a staff work schedule shift."""
        # Ensure employee profile exists
        profile = EmployeeService.get_profile_by_id(employee_id)

        # Validate no conflicting schedules
        validate_schedule(employee_id, work_date, start_time, end_time)

        sched = EmployeeSchedule(
            employee_id=employee_id,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            break_start=break_start,
            break_end=break_end,
            status=ScheduleStatus.SCHEDULED,
            notes=notes.strip() if notes else None,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(sched)
        db.session.commit()
        return sched

    @staticmethod
    def update_schedule(
        schedule_id,
        work_date=None,
        start_time=None,
        end_time=None,
        break_start=None,
        break_end=None,
        status=None,
        notes=None,
        updated_by_id=None,
    ):
        sched = db.session.get(EmployeeSchedule, schedule_id)
        if not sched:
            raise NotFoundError(f"Schedule #{schedule_id} not found.")

        target_date = work_date if work_date is not None else sched.work_date
        target_start = start_time if start_time is not None else sched.start_time
        target_end = end_time if end_time is not None else sched.end_time

        validate_schedule(
            employee_id=sched.employee_id,
            work_date=target_date,
            start_time=target_start,
            end_time=target_end,
            schedule_id=sched.id,
        )

        sched.work_date = target_date
        sched.start_time = target_start
        sched.end_time = target_end
        if break_start is not None:
            sched.break_start = break_start
        if break_end is not None:
            sched.break_end = break_end
        if status is not None and status in ScheduleStatus.ALL:
            sched.status = status
        if notes is not None:
            sched.notes = notes.strip() if notes else None

        sched.updated_by_id = updated_by_id
        sched.updated_at = datetime.utcnow()
        db.session.commit()
        return sched

    @staticmethod
    def cancel_schedule(schedule_id, updated_by_id=None):
        sched = db.session.get(EmployeeSchedule, schedule_id)
        if not sched:
            raise NotFoundError(f"Schedule #{schedule_id} not found.")
        sched.status = ScheduleStatus.CANCELLED
        sched.updated_by_id = updated_by_id
        sched.updated_at = datetime.utcnow()
        db.session.commit()
        return sched

    @staticmethod
    def get_schedules_paginated(
        page=1,
        per_page=20,
        employee_id=None,
        start_date=None,
        end_date=None,
        status=None,
    ):
        query = EmployeeSchedule.query
        if employee_id:
            query = query.filter(EmployeeSchedule.employee_id == employee_id)
        if start_date:
            query = query.filter(EmployeeSchedule.work_date >= start_date)
        if end_date:
            query = query.filter(EmployeeSchedule.work_date <= end_date)
        if status:
            query = query.filter(EmployeeSchedule.status == status)

        query = query.order_by(EmployeeSchedule.work_date.desc(), EmployeeSchedule.start_time.asc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_today_schedules_for_user(user_id, today_date=None):
        """Get scheduled shifts for a user on a given date (defaults to today)."""
        if today_date is None:
            today_date = date.today()
        profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return []
        return EmployeeSchedule.query.filter(
            EmployeeSchedule.employee_id == profile.id,
            EmployeeSchedule.work_date == today_date,
            EmployeeSchedule.status != ScheduleStatus.CANCELLED,
        ).order_by(EmployeeSchedule.start_time.asc()).all()

    # -------------------------------------------------------------
    # Time Attendance Methods
    # -------------------------------------------------------------

    @staticmethod
    def get_active_clock_in(user_id):
        """Get current unclosed attendance shift for a user."""
        return ShiftAttendance.query.filter_by(user_id=user_id, clock_out=None).first()

    @staticmethod
    def clock_in(user_id, schedule_id=None, notes=""):
        """Clock in using server-authoritative timestamp."""
        validate_can_clock_in(user_id)
        now_dt = datetime.utcnow()
        today_d = now_dt.date()

        profile = EmployeeService.get_or_create_profile(user_id)

        # Look up schedule if not explicitly given
        target_sched = None
        if schedule_id:
            target_sched = db.session.get(EmployeeSchedule, schedule_id)
        else:
            # Auto-find matching schedule for today
            today_schedules = EmployeeSchedule.query.filter(
                EmployeeSchedule.employee_id == profile.id,
                EmployeeSchedule.work_date == today_d,
                EmployeeSchedule.status == ScheduleStatus.SCHEDULED,
            ).order_by(EmployeeSchedule.start_time.asc()).all()

            if today_schedules:
                target_sched = today_schedules[0]

        sched_id = target_sched.id if target_sched else None
        sched_start = target_sched.start_time if target_sched else None
        sched_end = target_sched.end_time if target_sched else None

        att = ShiftAttendance(
            user_id=user_id,
            employee_id=profile.id,
            schedule_id=sched_id,
            attendance_date=today_d,
            scheduled_start=sched_start,
            scheduled_end=sched_end,
            clock_in=now_dt,
            notes=notes.strip() if notes else None,
            created_at=now_dt,
            updated_at=now_dt,
        )
        att.calculate_metrics()

        db.session.add(att)
        db.session.commit()
        return att

    @staticmethod
    def clock_out(user_id, notes=""):
        """Clock out using server-authoritative timestamp."""
        att = validate_can_clock_out(user_id)
        now_dt = datetime.utcnow()
        att.clock_out = now_dt
        att.updated_at = now_dt

        # Recalculate metrics
        att.calculate_metrics()

        if notes:
            att.notes = f"{att.notes} | Out Note: {notes.strip()}" if att.notes else notes.strip()

        # Update schedule status if linked
        if att.schedule:
            att.schedule.status = ScheduleStatus.COMPLETED

        db.session.commit()
        return att

    @staticmethod
    def start_break(user_id):
        """Start a break during active shift."""
        att = validate_can_start_break(user_id)
        now_dt = datetime.utcnow()
        att.break_start_at = now_dt
        att.break_end_at = None
        att.updated_at = now_dt
        db.session.commit()
        return att

    @staticmethod
    def end_break(user_id):
        """End an ongoing break during active shift."""
        att = validate_can_end_break(user_id)
        now_dt = datetime.utcnow()
        att.break_end_at = now_dt
        att.updated_at = now_dt
        att.calculate_metrics()
        db.session.commit()
        return att

    @staticmethod
    def correct_attendance(attendance_id, clock_in, clock_out, status, reason, manager_id):
        """
        Manager manual correction of an attendance record.
        Mandatory reason and manager audit trail.
        """
        validate_attendance_correction(clock_in, clock_out, reason)

        att = db.session.get(ShiftAttendance, attendance_id)
        if not att:
            raise NotFoundError(f"Attendance record #{attendance_id} not found.")

        old_in = att.clock_in.isoformat() if att.clock_in else "None"
        old_out = att.clock_out.isoformat() if att.clock_out else "None"

        att.clock_in = clock_in
        att.clock_out = clock_out
        att.attendance_date = clock_in.date()
        if status and status in AttendanceStatus.ALL:
            att.status = status
        else:
            att.status = AttendanceStatus.CORRECTED

        att.corrected_by_id = manager_id
        att.correction_reason = reason.strip()
        att.updated_at = datetime.utcnow()

        # Calculate metrics with new timestamps
        att.calculate_metrics()
        # Retain status as CORRECTED if desired
        att.status = AttendanceStatus.CORRECTED

        db.session.commit()

        # Audit log entry
        AuditLog.log(
            action="ATTENDANCE_CORRECTED",
            user_id=manager_id,
            details=(
                f"Shift #{attendance_id} for user {att.user_id} corrected. "
                f"Previous: ({old_in} - {old_out}), New: ({clock_in.isoformat()} - {clock_out.isoformat() if clock_out else 'None'}). "
                f"Reason: {reason}"
            ),
        )

        return att

    @staticmethod
    def mark_absent(schedule_id, notes="", manager_id=None):
        """Mark a scheduled shift as absent and record attendance entry."""
        sched = db.session.get(EmployeeSchedule, schedule_id)
        if not sched:
            raise NotFoundError(f"Schedule #{schedule_id} not found.")

        sched.status = ScheduleStatus.ABSENT
        sched.updated_by_id = manager_id
        sched.updated_at = datetime.utcnow()

        # Create or update absent attendance record
        att = ShiftAttendance.query.filter_by(schedule_id=sched.id).first()
        if not att:
            att = ShiftAttendance(
                user_id=sched.employee_profile.user_id,
                employee_id=sched.employee_id,
                schedule_id=sched.id,
                attendance_date=sched.work_date,
                scheduled_start=sched.start_time,
                scheduled_end=sched.end_time,
                clock_in=datetime.combine(sched.work_date, sched.start_time),
                clock_out=datetime.combine(sched.work_date, sched.start_time),
                total_hours=0.0,
                worked_minutes=0,
                status=AttendanceStatus.ABSENT,
                notes=notes.strip() if notes else "Marked absent by manager",
                corrected_by_id=manager_id,
                correction_reason=notes.strip() or "Shift marked absent",
            )
            db.session.add(att)
        else:
            att.status = AttendanceStatus.ABSENT
            att.total_hours = 0.0
            att.worked_minutes = 0
            att.notes = notes.strip() if notes else att.notes

        db.session.commit()
        return sched

    @staticmethod
    def get_attendances_paginated(
        page=1,
        per_page=20,
        employee_id=None,
        user_id=None,
        date_from=None,
        date_to=None,
        status=None,
    ):
        query = ShiftAttendance.query
        if employee_id:
            query = query.filter(ShiftAttendance.employee_id == employee_id)
        if user_id:
            query = query.filter(ShiftAttendance.user_id == user_id)
        if date_from:
            query = query.filter(
                or_(
                    ShiftAttendance.attendance_date >= date_from,
                    ShiftAttendance.clock_in >= datetime.combine(date_from, time.min),
                )
            )
        if date_to:
            query = query.filter(
                or_(
                    ShiftAttendance.attendance_date <= date_to,
                    ShiftAttendance.clock_in <= datetime.combine(date_to, time.max),
                )
            )
        if status:
            query = query.filter(ShiftAttendance.status == status)

        query = query.order_by(ShiftAttendance.clock_in.desc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_attendance_summary(start_date=None, end_date=None, employee_id=None):
        """
        Aggregate attendance KPIs: total hours, total shifts, late count, absent count, labor cost.
        """
        query = ShiftAttendance.query
        if employee_id:
            query = query.filter(ShiftAttendance.employee_id == employee_id)
        if start_date:
            query = query.filter(ShiftAttendance.clock_in >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(ShiftAttendance.clock_in <= datetime.combine(end_date, time.max))

        records = query.all()
        total_shifts = len(records)
        total_hours = sum(r.total_hours for r in records)
        late_count = sum(1 for r in records if r.late_minutes > 0 or r.status == AttendanceStatus.LATE)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        on_time_count = sum(1 for r in records if r.late_minutes == 0 and r.status in (AttendanceStatus.PRESENT, AttendanceStatus.EARLY_DEPARTURE))

        on_time_pct = round((on_time_count / total_shifts * 100), 1) if total_shifts > 0 else 100.0

        # Estimate labor cost using employee hourly rate
        total_labor_cost = Decimal("0.00")
        for r in records:
            rate = Decimal(str(r.employee_profile.hourly_rate)) if r.employee_profile and r.employee_profile.hourly_rate else Decimal("15.00")
            hours_dec = Decimal(str(round(r.total_hours, 2)))
            total_labor_cost += (rate * hours_dec)

        return {
            "total_shifts": total_shifts,
            "total_hours": round(total_hours, 2),
            "late_count": late_count,
            "absent_count": absent_count,
            "on_time_percentage": on_time_pct,
            "total_labor_cost": total_labor_cost.quantize(Decimal("0.01")),
        }
