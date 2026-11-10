import pytest
from datetime import date
from app.extensions import db
from app.modules.employees.models import ShiftAttendance, EmployeeProfile
from app.modules.employees.services import EmployeeService


def test_unauthenticated_staff_routes_redirect(client):
    """Test unauthenticated users are redirected to login."""
    routes = [
        "/staff/",
        "/staff/my-shifts",
        "/staff/schedules",
        "/staff/schedules/create",
        "/staff/attendance",
        "/staff/export/attendance-csv",
    ]
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 302
        assert "/auth/login" in resp.location


def test_staff_role_forbidden_on_manager_endpoints(client, staff_user, manager_user):
    """Test staff role cannot access manager-only routes."""
    client.post("/auth/login", data={"username": staff_user.username, "password": "Staff123!"}, follow_redirects=True)

    # 1. Profile edit endpoint
    resp_prof = client.get(f"/staff/{staff_user.id}/profile")
    assert resp_prof.status_code == 403

    # 2. Schedule creation form
    resp_sched = client.get("/staff/schedules/create")
    assert resp_sched.status_code == 403

    # 3. Attendance correction
    resp_corr = client.post("/staff/attendance/1/correct", data={"reason": "Unauthorized"})
    assert resp_corr.status_code == 403

    # 4. Attendance board and CSV export
    resp_att = client.get("/staff/attendance")
    assert resp_att.status_code == 403
    resp_csv = client.get("/staff/export/attendance-csv")
    assert resp_csv.status_code == 403


def test_cashier_and_barista_can_access_self_service(client, cashier_user, barista_user):
    """Test cashier and barista have appropriate access to their own shifts and schedule view."""
    # Cashier
    client.post("/auth/login", data={"username": cashier_user.username, "password": "Cashier123!"}, follow_redirects=True)
    resp = client.get("/staff/my-shifts")
    assert resp.status_code == 200

    resp_sched = client.get("/staff/schedules")
    assert resp_sched.status_code == 200

    client.get("/auth/logout")

    # Barista
    client.post("/auth/login", data={"username": barista_user.username, "password": "Barista123!"}, follow_redirects=True)
    resp_b = client.get("/staff/my-shifts")
    assert resp_b.status_code == 200

    resp_b_sched = client.get("/staff/schedules")
    assert resp_b_sched.status_code == 200


def test_attendance_csv_formula_injection_sanitization(client, manager_user, staff_user):
    """Test CSV export sanitizes potential Excel/Calc formula injection characters (=, +, -, @)."""
    profile = EmployeeService.get_or_create_profile(staff_user.id)

    # Injected dangerous note
    att = ShiftAttendance(
        user_id=staff_user.id,
        employee_id=profile.id,
        attendance_date=date.today(),
        clock_in=db.func.now(),
        notes="=CMD('calc')|'A0'!A0",
        correction_reason="+SUM(1,2)",
    )
    db.session.add(att)
    db.session.commit()

    client.post("/auth/login", data={"username": manager_user.username, "password": "Manager123!"}, follow_redirects=True)

    resp = client.get("/staff/export/attendance-csv")
    assert resp.status_code == 200
    csv_text = resp.data.decode("utf-8")

    # Check that dangerous formula symbols are prefixed with a single quote
    assert "'=CMD('calc')" in csv_text
    assert "'+SUM(1,2)" in csv_text
