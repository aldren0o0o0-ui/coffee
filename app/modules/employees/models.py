from datetime import datetime, date, time
from decimal import Decimal
from app.extensions import db


class EmploymentStatus:
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"
    SUSPENDED = "SUSPENDED"

    ALL = [ACTIVE, ON_LEAVE, TERMINATED, SUSPENDED]


class ScheduleStatus:
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    ABSENT = "ABSENT"
    CANCELLED = "CANCELLED"

    ALL = [SCHEDULED, COMPLETED, ABSENT, CANCELLED]


class AttendanceStatus:
    PRESENT = "PRESENT"
    LATE = "LATE"
    EARLY_DEPARTURE = "EARLY_DEPARTURE"
    LATE_AND_EARLY_DEPARTURE = "LATE_AND_EARLY_DEPARTURE"
    ABSENT = "ABSENT"
    ON_LEAVE = "ON_LEAVE"
    CORRECTED = "CORRECTED"

    ALL = [
        PRESENT,
        LATE,
        EARLY_DEPARTURE,
        LATE_AND_EARLY_DEPARTURE,
        ABSENT,
        ON_LEAVE,
        CORRECTED,
    ]


class EmployeeProfile(db.Model):
    __tablename__ = "employee_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    position = db.Column(db.String(64), default="Staff", nullable=False)
    employment_status = db.Column(db.String(32), default=EmploymentStatus.ACTIVE, nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)
    hourly_rate = db.Column(db.Numeric(10, 2), default=Decimal("15.00"), nullable=False)
    hire_date = db.Column(db.Date, default=date.today, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    emergency_contact = db.Column(db.String(120), nullable=True)
    emergency_contact_phone = db.Column(db.String(32), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("employee_profile", uselist=False, cascade="all, delete-orphan"))
    schedules = db.relationship("EmployeeSchedule", backref="employee_profile", cascade="all, delete-orphan", lazy="dynamic", foreign_keys="EmployeeSchedule.employee_id")
    attendances = db.relationship("ShiftAttendance", backref="employee_profile", cascade="all, delete-orphan", lazy="dynamic", foreign_keys="ShiftAttendance.employee_id")

    @property
    def full_name(self):
        return self.user.full_name if self.user else f"Employee #{self.id}"

    @property
    def email(self):
        return self.user.email if self.user else ""

    @property
    def role(self):
        return self.user.role if self.user else ""

    @property
    def is_active(self):
        return self.employment_status == EmploymentStatus.ACTIVE and (self.user.is_active if self.user else False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee_code": self.employee_code,
            "full_name": self.full_name,
            "email": self.email,
            "position": self.position,
            "role": self.role,
            "employment_status": self.employment_status,
            "phone": self.phone,
            "hourly_rate": float(self.hourly_rate) if self.hourly_rate is not None else 0.0,
            "hire_date": self.hire_date.strftime("%Y-%m-%d") if self.hire_date else None,
            "address": self.address,
            "emergency_contact": self.emergency_contact,
            "emergency_contact_phone": self.emergency_contact_phone,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EmployeeProfile id={self.id} code='{self.employee_code}' name='{self.full_name}'>"


class EmployeeSchedule(db.Model):
    __tablename__ = "employee_schedules"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    break_start = db.Column(db.Time, nullable=True)
    break_end = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(32), default=ScheduleStatus.SCHEDULED, nullable=False, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    attendances = db.relationship("ShiftAttendance", backref="schedule", lazy="dynamic", foreign_keys="ShiftAttendance.schedule_id")

    @property
    def scheduled_hours(self) -> float:
        """Calculate scheduled duration in hours minus break if specified."""
        if not self.start_time or not self.end_time:
            return 0.0
        start_min = self.start_time.hour * 60 + self.start_time.minute
        end_min = self.end_time.hour * 60 + self.end_time.minute
        if end_min < start_min:  # overnight
            total_min = (24 * 60 - start_min) + end_min
        else:
            total_min = end_min - start_min

        if self.break_start and self.break_end:
            b_start = self.break_start.hour * 60 + self.break_start.minute
            b_end = self.break_end.hour * 60 + self.break_end.minute
            b_min = b_end - b_start if b_end >= b_start else (24 * 60 - b_start) + b_end
            total_min = max(0, total_min - b_min)

        return round(total_min / 60.0, 2)

    @property
    def formatted_time_range(self) -> str:
        s = self.start_time.strftime("%I:%M %p") if self.start_time else ""
        e = self.end_time.strftime("%I:%M %p") if self.end_time else ""
        return f"{s} - {e}"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee_profile.full_name if self.employee_profile else "Unknown",
            "employee_code": self.employee_profile.employee_code if self.employee_profile else "",
            "work_date": self.work_date.strftime("%Y-%m-%d") if self.work_date else "",
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else "",
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else "",
            "break_start": self.break_start.strftime("%H:%M") if self.break_start else None,
            "break_end": self.break_end.strftime("%H:%M") if self.break_end else None,
            "scheduled_hours": self.scheduled_hours,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EmployeeSchedule id={self.id} emp={self.employee_id} date={self.work_date} status='{self.status}'>"


class ShiftAttendance(db.Model):
    __tablename__ = "shift_attendances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("employee_schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    attendance_date = db.Column(db.Date, nullable=True, index=True)
    scheduled_start = db.Column(db.Time, nullable=True)
    scheduled_end = db.Column(db.Time, nullable=True)
    clock_in = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    clock_out = db.Column(db.DateTime, nullable=True)
    break_start_at = db.Column(db.DateTime, nullable=True)
    break_end_at = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, default=0.0, nullable=False)
    worked_minutes = db.Column(db.Integer, default=0, nullable=False)
    late_minutes = db.Column(db.Integer, default=0, nullable=False)
    undertime_minutes = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(32), default=AttendanceStatus.PRESENT, nullable=False, index=True)
    notes = db.Column(db.String(255), nullable=True)
    corrected_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    correction_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], backref="attendances")
    corrected_by = db.relationship("User", foreign_keys=[corrected_by_id])

    @property
    def is_active(self) -> bool:
        return self.clock_out is None

    @property
    def is_on_break(self) -> bool:
        return self.break_start_at is not None and self.break_end_at is None

    @property
    def employee_name(self) -> str:
        if self.employee_profile and self.employee_profile.user:
            return self.employee_profile.user.full_name
        if self.user:
            return self.user.full_name
        return "Employee"

    @property
    def employee_code(self) -> str:
        if self.employee_profile:
            return self.employee_profile.employee_code
        return ""

    def calculate_metrics(self):
        """
        Recalculate worked_minutes, total_hours, late_minutes, undertime_minutes, and status.
        """
        if self.clock_in and self.clock_out:
            total_seconds = (self.clock_out - self.clock_in).total_seconds()
            # Deduct break duration if break was taken
            if self.break_start_at and self.break_end_at:
                break_seconds = (self.break_end_at - self.break_start_at).total_seconds()
                total_seconds = max(0, total_seconds - break_seconds)

            self.worked_minutes = int(total_seconds // 60)
            self.total_hours = round(total_seconds / 3600.0, 2)
        elif self.clock_in and not self.clock_out:
            # Active shift
            total_seconds = (datetime.utcnow() - self.clock_in).total_seconds()
            if self.break_start_at and self.break_end_at:
                break_seconds = (self.break_end_at - self.break_start_at).total_seconds()
                total_seconds = max(0, total_seconds - break_seconds)
            self.worked_minutes = int(total_seconds // 60)
            self.total_hours = round(total_seconds / 3600.0, 2)

        if self.scheduled_start and self.clock_in:
            in_time = self.clock_in.time()
            in_min = in_time.hour * 60 + in_time.minute
            sched_min = self.scheduled_start.hour * 60 + self.scheduled_start.minute
            diff = in_min - sched_min
            # 5 minutes grace period
            if diff > 5:
                self.late_minutes = diff
            else:
                self.late_minutes = 0
        elif self.late_minutes is None:
            self.late_minutes = 0

        if self.scheduled_end and self.clock_out:
            out_time = self.clock_out.time()
            out_min = out_time.hour * 60 + out_time.minute
            sched_end_min = self.scheduled_end.hour * 60 + self.scheduled_end.minute
            diff_early = sched_end_min - out_min
            # 5 minutes grace period for early departure
            if diff_early > 5:
                self.undertime_minutes = diff_early
            else:
                self.undertime_minutes = 0
        elif self.undertime_minutes is None:
            self.undertime_minutes = 0

        # Status determination if not manually corrected or leave
        late_min = self.late_minutes or 0
        early_min = self.undertime_minutes or 0
        if self.status not in (AttendanceStatus.CORRECTED, AttendanceStatus.ON_LEAVE, AttendanceStatus.ABSENT):
            is_late = late_min > 0
            is_early = early_min > 0
            if is_late and is_early:
                self.status = AttendanceStatus.LATE_AND_EARLY_DEPARTURE
            elif is_late:
                self.status = AttendanceStatus.LATE
            elif is_early:
                self.status = AttendanceStatus.EARLY_DEPARTURE
            else:
                self.status = AttendanceStatus.PRESENT

        return self.total_hours

    def calculate_hours(self):
        """Backward compatibility helper for existing codebase."""
        return self.calculate_metrics()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee_id": self.employee_id,
            "schedule_id": self.schedule_id,
            "employee_name": self.employee_name,
            "employee_code": self.employee_code,
            "attendance_date": self.attendance_date.strftime("%Y-%m-%d") if self.attendance_date else None,
            "clock_in": self.clock_in.strftime("%Y-%m-%d %H:%M:%S") if self.clock_in else None,
            "clock_out": self.clock_out.strftime("%Y-%m-%d %H:%M:%S") if self.clock_out else None,
            "break_start_at": self.break_start_at.strftime("%Y-%m-%d %H:%M:%S") if self.break_start_at else None,
            "break_end_at": self.break_end_at.strftime("%Y-%m-%d %H:%M:%S") if self.break_end_at else None,
            "is_on_break": self.is_on_break,
            "total_hours": self.total_hours,
            "worked_minutes": self.worked_minutes,
            "late_minutes": self.late_minutes,
            "undertime_minutes": self.undertime_minutes,
            "status": self.status,
            "notes": self.notes,
            "corrected_by_id": self.corrected_by_id,
            "correction_reason": self.correction_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<ShiftAttendance id={self.id} user={self.user_id} date={self.attendance_date} status='{self.status}'>"
