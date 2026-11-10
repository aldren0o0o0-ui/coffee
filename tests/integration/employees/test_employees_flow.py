import pytest
from datetime import date, time, timedelta
from app.extensions import db
from app.modules.employees.models import (
    EmployeeProfile,
    EmployeeSchedule,
    ShiftAttendance,
    ScheduleStatus,
    AttendanceStatus,
)
from app.modules.employees.services import EmployeeService


def test_staff_directory_view(client, manager_user, staff_user):
    """Test manager accessing the staff directory."""
    # Login as manager
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    resp = client.get("/staff/")
    assert resp.status_code == 200
    assert b"Staff Directory &amp; Roster" in resp.data or b"Staff Directory & Roster" in resp.data
    assert staff_user.first_name.encode() in resp.data


def test_staff_self_service_redirect_and_my_shifts(client, staff_user):
    """Test non-manager accessing /staff/ is redirected to /staff/my-shifts."""
    client.post("/auth/login", data={"username": staff_user.username, "password": "Staff123!"}, follow_redirects=True)

    # Accessing /staff/ redirects to /staff/my-shifts
    resp = client.get("/staff/", follow_redirects=True)
    assert resp.status_code == 200
    assert b"My Shifts &amp; Time Clock" in resp.data or b"My Shifts & Time Clock" in resp.data


def test_profile_update_flow(client, manager_user, staff_user):
    """Test updating employee profile via HTTP POST."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    resp = client.post(
        f"/staff/{staff_user.id}/profile",
        data={
            "position": "Shift Supervisor",
            "employment_status": "ACTIVE",
            "hourly_rate": "22.50",
            "hire_date": "2026-01-15",
            "phone": "+1-555-4433",
            "address": "456 Artisan Blvd",
            "emergency_contact": "Bob Smith",
            "emergency_contact_phone": "+1-555-9988",
            "notes": "Barista level 2 certified",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    profile = EmployeeService.get_or_create_profile(staff_user.id)
    assert profile.position == "Shift Supervisor"
    assert float(profile.hourly_rate) == 22.50
    assert profile.phone == "+1-555-4433"


def test_schedule_creation_and_conflict_ui_flow(client, manager_user, staff_user):
    """Test creating schedules and handling validation errors via HTTP."""
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    profile = EmployeeService.get_or_create_profile(staff_user.id)
    work_day = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    # 1. Successful schedule creation
    resp1 = client.post(
        "/staff/schedules/create",
        data={
            "employee_id": profile.id,
            "work_date": work_day,
            "start_time": "08:00",
            "end_time": "16:00",
            "break_start": "12:00",
            "break_end": "12:30",
            "notes": "Opening shift",
        },
        follow_redirects=True,
    )
    assert resp1.status_code == 200
    assert b"Shift schedule created successfully" in resp1.data

    # 2. Conflicting schedule on same day/time (must show error message)
    resp2 = client.post(
        "/staff/schedules/create",
        data={
            "employee_id": profile.id,
            "work_date": work_day,
            "start_time": "14:00",
            "end_time": "20:00",
            "notes": "Overlapping afternoon",
        },
        follow_redirects=True,
    )
    assert resp2.status_code == 200
    assert b"conflicts with an existing shift" in resp2.data


def test_clock_in_break_and_clock_out_flow(client, staff_user):
    """Test full employee self-service time clock cycle via HTTP POST."""
    client.post("/auth/login", data={"username": staff_user.username, "password": "Staff123!"}, follow_redirects=True)

    # 1. Clock in
    resp_in = client.post("/staff/clock-in", data={"notes": "Starting barista shift"}, follow_redirects=True)
    assert resp_in.status_code == 200
    assert b"Clocked in at" in resp_in.data

    att = EmployeeService.get_active_clock_in(staff_user.id)
    assert att is not None
    assert att.clock_out is None

    # 2. Start break
    resp_b_start = client.post("/staff/break/start", follow_redirects=True)
    assert resp_b_start.status_code == 200
    assert b"Break started" in resp_b_start.data
    assert att.is_on_break is True

    # 3. End break
    resp_b_end = client.post("/staff/break/end", follow_redirects=True)
    assert resp_b_end.status_code == 200
    assert b"Break ended" in resp_b_end.data
    assert att.is_on_break is False

    # 4. Clock out
    resp_out = client.post("/staff/clock-out", data={"notes": "Shift ended"}, follow_redirects=True)
    assert resp_out.status_code == 200
    assert b"Clock-out recorded" in resp_out.data

    assert EmployeeService.get_active_clock_in(staff_user.id) is None


def test_manager_correction_and_csv_export(client, manager_user, staff_user):
    """Test manager attendance correction and sanitized CSV export."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)
    today = date.today()

    # Clock in directly
    att = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        attendance_date=today,
        clock_in=db.func.now(),
        notes="Testing shift",
    )
    db.session.add(att)
    db.session.commit()

    # Login as manager
    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    # Submit correction
    resp_corr = client.post(
        f"/staff/attendance/{att.id}/correct",
        data={
            "clock_in": f"{today.strftime('%Y-%m-%d')} 08:00",
            "clock_out": f"{today.strftime('%Y-%m-%d')} 16:00",
            "reason": "Corrected missed punch verified with morning camera log",
        },
        follow_redirects=True,
    )
    assert resp_corr.status_code == 200
    assert b"Shift attendance record corrected" in resp_corr.data

    # Verify CSV export
    csv_resp = client.get("/staff/export/attendance-csv")
    assert csv_resp.status_code == 200
    assert csv_resp.mimetype == "text/csv"
    assert b"Employee Code,Employee Name,Date" in csv_resp.data
    assert staff_user.full_name.encode() in csv_resp.data
