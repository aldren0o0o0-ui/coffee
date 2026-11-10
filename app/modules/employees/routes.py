from flask import Blueprint, request, render_template, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import csv
import io
from app.core.decorators import roles_required
from app.core.permissions import Roles, Permissions
from app.modules.employees.services import EmployeeService
from app.modules.employees.models import (
    EmployeeProfile,
    EmployeeSchedule,
    ShiftAttendance,
    EmploymentStatus,
    ScheduleStatus,
    AttendanceStatus,
)
from app.modules.users.services import UserService
from app.modules.users.models import User
from app.core.exceptions import AppException, ValidationError, NotFoundError
from app.core.utilities import format_datetime, format_currency

employees_bp = Blueprint("employees", __name__)


def sanitize_csv_field(val):
    """Sanitize CSV cell to prevent spreadsheet formula injection."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


@employees_bp.route("/", methods=["GET"])
@login_required
def index():
    # If user is not manager/owner, redirect to personal self-service portal
    if not current_user.is_manager_or_above:
        return redirect(url_for("employees.my_shifts"))

    status_filter = request.args.get("status", "")
    role_filter = request.args.get("role", "")
    search_q = request.args.get("q", "").strip().lower()

    query = User.query.filter(User.role != Roles.OWNER)

    if role_filter:
        query = query.filter(User.role == role_filter)

    users = query.order_by(User.first_name.asc()).all()

    # Apply search and employment status filtering in Python or query
    filtered_users = []
    for u in users:
        p = EmployeeService.get_or_create_profile(u.id)
        if status_filter and p.employment_status != status_filter:
            continue
        if search_q:
            match = (
                search_q in u.full_name.lower()
                or search_q in u.email.lower()
                or search_q in p.employee_code.lower()
                or search_q in (p.position or "").lower()
            )
            if not match:
                continue
        filtered_users.append(u)

    active_shift = EmployeeService.get_active_clock_in(current_user.id)

    # Active staff currently on shift across the cafe
    active_shifts = ShiftAttendance.query.filter_by(clock_out=None).all()
    on_duty_count = len(active_shifts)

    # Today's scheduled shifts count
    today_schedules_count = EmployeeSchedule.query.filter_by(
        work_date=date.today(),
        status=ScheduleStatus.SCHEDULED,
    ).count()

    total_active_staff = len([u for u in users if u.is_active])

    return render_template(
        "employees/index.html",
        users=filtered_users,
        active_clock=active_shift,
        on_duty_count=on_duty_count,
        today_schedules_count=today_schedules_count,
        total_active_staff=total_active_staff,
        selected_status=status_filter,
        selected_role=role_filter,
        search_query=search_q,
    )


@employees_bp.route("/my-shifts", methods=["GET"])
@login_required
def my_shifts():
    """Personal self-service schedule and attendance portal for staff."""
    profile = EmployeeService.get_or_create_profile(current_user.id)
    today = date.today()

    active_clock = EmployeeService.get_active_clock_in(current_user.id)

    # Today's scheduled shift for user
    today_shifts = EmployeeService.get_today_schedules_for_user(current_user.id, today)

    # Upcoming 7-day schedule
    upcoming_schedules = EmployeeSchedule.query.filter(
        EmployeeSchedule.employee_id == profile.id,
        EmployeeSchedule.work_date >= today,
        EmployeeSchedule.work_date <= today + timedelta(days=7),
        EmployeeSchedule.status != ScheduleStatus.CANCELLED,
    ).order_by(EmployeeSchedule.work_date.asc(), EmployeeSchedule.start_time.asc()).all()

    # Recent attendance records (last 14 days)
    recent_attendances = ShiftAttendance.query.filter(
        ShiftAttendance.user_id == current_user.id,
        ShiftAttendance.clock_in >= datetime.combine(today - timedelta(days=14), time.min),
    ).order_by(ShiftAttendance.clock_in.desc()).limit(15).all()

    total_hours_this_week = sum(
        (Decimal(str(round(a.total_hours, 2))) for a in recent_attendances
        if a.attendance_date and a.attendance_date >= (today - timedelta(days=today.weekday()))),
        Decimal("0.00")
    )
    est_weekly_earnings = (total_hours_this_week * (profile.hourly_rate or Decimal("15.00"))).quantize(Decimal("0.01"))

    return render_template(
        "employees/my_shifts.html",
        profile=profile,
        active_clock=active_clock,
        today_shifts=today_shifts,
        upcoming_schedules=upcoming_schedules,
        recent_attendances=recent_attendances,
        total_hours_this_week=float(total_hours_this_week),
        est_weekly_earnings=est_weekly_earnings,
    )


@employees_bp.route("/<int:user_id>/profile", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def profile(user_id):
    user = UserService.get_user_by_id(user_id)
    prof = EmployeeService.get_or_create_profile(user_id)

    if request.method == "POST":
        data = request.form
        date_str = data.get("hire_date")
        hire_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None

        try:
            EmployeeService.update_profile(
                user_id=user.id,
                phone=data.get("phone"),
                hourly_rate=data.get("hourly_rate", 15.0),
                hire_date=hire_date,
                emergency_contact=data.get("emergency_contact"),
                emergency_contact_phone=data.get("emergency_contact_phone"),
                position=data.get("position"),
                employment_status=data.get("employment_status"),
                address=data.get("address"),
                notes=data.get("notes"),
            )
            flash(f"Profile and compensation updated for {user.full_name}.", "success")
            return redirect(url_for("employees.index"))
        except AppException as e:
            flash(e.message, "danger")

    return render_template(
        "employees/profile.html",
        user=user,
        profile=prof,
        employment_statuses=EmploymentStatus.ALL,
    )


@employees_bp.route("/schedules", methods=["GET"])
@login_required
def schedules():
    """Shift schedule master calendar/table."""
    page = request.args.get("page", 1, type=int)
    emp_id = request.args.get("employee_id", type=int)
    start_str = request.args.get("start_date", "")
    end_str = request.args.get("end_date", "")
    status = request.args.get("status", "")

    # Default to current week if dates not provided
    today = date.today()
    if not start_str:
        start_date = today - timedelta(days=today.weekday())
        start_str = start_date.strftime("%Y-%m-%d")
    else:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()

    if not end_str:
        end_date = start_date + timedelta(days=6)
        end_str = end_date.strftime("%Y-%m-%d")
    else:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()

    pagination = EmployeeService.get_schedules_paginated(
        page=page,
        per_page=25,
        employee_id=emp_id,
        start_date=start_date,
        end_date=end_date,
        status=status if status else None,
    )

    profiles = EmployeeService.get_all_profiles(active_only=True)

    return render_template(
        "employees/schedules.html",
        pagination=pagination,
        profiles=profiles,
        selected_emp_id=emp_id,
        start_date=start_str,
        end_date=end_str,
        selected_status=status,
        schedule_statuses=ScheduleStatus.ALL,
    )


@employees_bp.route("/schedules/create", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def create_schedule():
    """Create a new shift schedule."""
    if request.method == "POST":
        data = request.form
        emp_id = data.get("employee_id", type=int)
        work_date_str = data.get("work_date")
        start_time_str = data.get("start_time")
        end_time_str = data.get("end_time")
        notes = data.get("notes", "")

        try:
            if not work_date_str or not start_time_str or not end_time_str:
                raise ValidationError("Work date, start time, and end time are required.")

            work_date = datetime.strptime(work_date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()

            b_start = None
            b_end = None
            if data.get("break_start") and data.get("break_end"):
                b_start = datetime.strptime(data.get("break_start"), "%H:%M").time()
                b_end = datetime.strptime(data.get("break_end"), "%H:%M").time()

            sched = EmployeeService.create_schedule(
                employee_id=emp_id,
                work_date=work_date,
                start_time=start_time,
                end_time=end_time,
                break_start=b_start,
                break_end=b_end,
                notes=notes,
                created_by_id=current_user.id,
            )
            flash(f"Shift schedule created successfully for {sched.employee_profile.full_name}.", "success")
            return redirect(url_for("employees.schedules", start_date=work_date_str, end_date=work_date_str))
        except AppException as e:
            flash(e.message, "danger")

    profiles = EmployeeService.get_all_profiles(active_only=True)
    return render_template("employees/schedule_form.html", profiles=profiles, schedule=None)


@employees_bp.route("/schedules/<int:schedule_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def edit_schedule(schedule_id):
    sched = EmployeeService.get_schedules_paginated(employee_id=None).items
    # Use db directly for lookup
    from app.extensions import db
    sched = db.session.get(EmployeeSchedule, schedule_id)
    if not sched:
        flash(f"Schedule #{schedule_id} not found.", "danger")
        return redirect(url_for("employees.schedules"))

    if request.method == "POST":
        data = request.form
        try:
            work_date = datetime.strptime(data.get("work_date"), "%Y-%m-%d").date() if data.get("work_date") else None
            start_time = datetime.strptime(data.get("start_time"), "%H:%M").time() if data.get("start_time") else None
            end_time = datetime.strptime(data.get("end_time"), "%H:%M").time() if data.get("end_time") else None

            b_start = None
            b_end = None
            if data.get("break_start") and data.get("break_end"):
                b_start = datetime.strptime(data.get("break_start"), "%H:%M").time()
                b_end = datetime.strptime(data.get("break_end"), "%H:%M").time()

            EmployeeService.update_schedule(
                schedule_id=sched.id,
                work_date=work_date,
                start_time=start_time,
                end_time=end_time,
                break_start=b_start,
                break_end=b_end,
                status=data.get("status"),
                notes=data.get("notes"),
                updated_by_id=current_user.id,
            )
            flash(f"Shift schedule updated successfully.", "success")
            return redirect(url_for("employees.schedules"))
        except AppException as e:
            flash(e.message, "danger")

    profiles = EmployeeService.get_all_profiles(active_only=True)
    return render_template("employees/schedule_form.html", profiles=profiles, schedule=sched)


@employees_bp.route("/schedules/<int:schedule_id>/cancel", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def cancel_schedule(schedule_id):
    try:
        EmployeeService.cancel_schedule(schedule_id, updated_by_id=current_user.id)
        flash("Shift schedule cancelled.", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(request.referrer or url_for("employees.schedules"))


@employees_bp.route("/schedules/<int:schedule_id>/mark-absent", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def mark_absent(schedule_id):
    notes = request.form.get("notes", "Marked absent by manager")
    try:
        EmployeeService.mark_absent(schedule_id, notes=notes, manager_id=current_user.id)
        flash("Shift marked as absent.", "warning")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(request.referrer or url_for("employees.schedules"))


@employees_bp.route("/attendance", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def attendance():
    page = request.args.get("page", 1, type=int)
    emp_id = request.args.get("employee_id", type=int)
    status_filter = request.args.get("status", "")
    start_str = request.args.get("start_date", "")
    end_str = request.args.get("end_date", "")

    today = date.today()
    if not start_str:
        date_from = today - timedelta(days=14)
        start_str = date_from.strftime("%Y-%m-%d")
    else:
        date_from = datetime.strptime(start_str, "%Y-%m-%d").date()

    if not end_str:
        date_to = today
        end_str = date_to.strftime("%Y-%m-%d")
    else:
        date_to = datetime.strptime(end_str, "%Y-%m-%d").date()

    pagination = EmployeeService.get_attendances_paginated(
        page=page,
        per_page=20,
        employee_id=emp_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter if status_filter else None,
    )

    summary = EmployeeService.get_attendance_summary(
        start_date=date_from,
        end_date=date_to,
        employee_id=emp_id,
    )

    profiles = EmployeeService.get_all_profiles()

    return render_template(
        "employees/attendance.html",
        pagination=pagination,
        summary=summary,
        profiles=profiles,
        selected_emp_id=emp_id,
        selected_status=status_filter,
        start_date=start_str,
        end_date=end_str,
        attendance_statuses=AttendanceStatus.ALL,
    )


@employees_bp.route("/attendance/<int:attendance_id>/correct", methods=["POST"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def correct_attendance(attendance_id):
    data = request.form
    clock_in_str = data.get("clock_in")
    clock_out_str = data.get("clock_out")
    reason = data.get("reason", "").strip()

    try:
        if not clock_in_str:
            raise ValidationError("Clock-in timestamp is required.")
        if not reason:
            raise ValidationError("A clear reason is required for manual attendance corrections.")

        clock_in = datetime.strptime(clock_in_str, "%Y-%m-%d %H:%M")
        clock_out = datetime.strptime(clock_out_str, "%Y-%m-%d %H:%M") if clock_out_str else None

        EmployeeService.correct_attendance(
            attendance_id=attendance_id,
            clock_in=clock_in,
            clock_out=clock_out,
            status=AttendanceStatus.CORRECTED,
            reason=reason,
            manager_id=current_user.id,
        )
        flash("Shift attendance record corrected with manager audit log.", "success")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(request.referrer or url_for("employees.attendance"))


@employees_bp.route("/clock-in", methods=["POST"])
@login_required
def clock_in():
    notes = request.form.get("notes", "")
    try:
        att = EmployeeService.clock_in(current_user.id, notes=notes)
        flash(f"Clocked in at {format_datetime(att.clock_in, '%I:%M %p')}. Have a great shift!", "success")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(request.referrer or url_for("employees.my_shifts"))


@employees_bp.route("/clock-out", methods=["POST"])
@login_required
def clock_out():
    notes = request.form.get("notes", "")
    try:
        att = EmployeeService.clock_out(current_user.id, notes=notes)
        flash(f"Clock-out recorded. Total shift time: {att.total_hours} hrs ({att.worked_minutes} mins).", "info")
    except AppException as e:
        flash(e.message, "danger")

    return redirect(request.referrer or url_for("employees.my_shifts"))


@employees_bp.route("/break/start", methods=["POST"])
@login_required
def start_break():
    try:
        EmployeeService.start_break(current_user.id)
        flash("Break started. Enjoy your break!", "info")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(request.referrer or url_for("employees.my_shifts"))


@employees_bp.route("/break/end", methods=["POST"])
@login_required
def end_break():
    try:
        EmployeeService.end_break(current_user.id)
        flash("Break ended. Welcome back to your shift!", "success")
    except AppException as e:
        flash(e.message, "danger")
    return redirect(request.referrer or url_for("employees.my_shifts"))


@employees_bp.route("/export/attendance-csv", methods=["GET"])
@login_required
@roles_required(Roles.OWNER, Roles.MANAGER)
def export_attendance_csv():
    start_str = request.args.get("start_date", "")
    end_str = request.args.get("end_date", "")
    emp_id = request.args.get("employee_id", type=int)

    date_from = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else None
    date_to = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else None

    # Fetch records (up to 1000)
    pagination = EmployeeService.get_attendances_paginated(
        page=1,
        per_page=1000,
        employee_id=emp_id,
        date_from=date_from,
        date_to=date_to,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee Code",
        "Employee Name",
        "Date",
        "Scheduled Start",
        "Scheduled End",
        "Clock In",
        "Clock Out",
        "Total Hours",
        "Worked Minutes",
        "Late Minutes",
        "Undertime Minutes",
        "Status",
        "Hourly Rate",
        "Est. Wage ($)",
        "Notes",
        "Correction Reason",
    ])

    for a in pagination.items:
        rate = float(a.employee_profile.hourly_rate) if a.employee_profile and a.employee_profile.hourly_rate else 15.0
        est_wage = round(a.total_hours * rate, 2)
        writer.writerow([
            sanitize_csv_field(a.employee_code),
            sanitize_csv_field(a.employee_name),
            sanitize_csv_field(a.attendance_date.strftime("%Y-%m-%d") if a.attendance_date else ""),
            sanitize_csv_field(a.scheduled_start.strftime("%H:%M") if a.scheduled_start else ""),
            sanitize_csv_field(a.scheduled_end.strftime("%H:%M") if a.scheduled_end else ""),
            sanitize_csv_field(a.clock_in.strftime("%Y-%m-%d %H:%M") if a.clock_in else ""),
            sanitize_csv_field(a.clock_out.strftime("%Y-%m-%d %H:%M") if a.clock_out else ""),
            a.total_hours,
            a.worked_minutes,
            a.late_minutes,
            a.undertime_minutes,
            sanitize_csv_field(a.status),
            rate,
            est_wage,
            sanitize_csv_field(a.notes or ""),
            sanitize_csv_field(a.correction_reason or ""),
        ])

    output.seek(0)
    filename = f"attendance_timesheets_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
