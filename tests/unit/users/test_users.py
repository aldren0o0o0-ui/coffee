"""Unit tests for User model and UserService (Phase 1 & 2)."""
import pytest
from app.modules.users.models import User
from app.modules.users.services import UserService
from app.core.permissions import Roles
from app.core.exceptions import AppException
from app.extensions import db


def test_user_model_full_name_property(app, owner_user):
    """User.full_name should concatenate first_name and last_name."""
    with app.app_context():
        assert owner_user.full_name == "Test Owner"


def test_user_model_is_owner_property(app, owner_user, barista_user):
    """is_owner and is_manager_or_above should reflect role hierarchy."""
    with app.app_context():
        assert owner_user.is_owner is True
        assert owner_user.is_manager_or_above is True
        assert barista_user.is_owner is False
        assert barista_user.is_manager_or_above is False


def test_user_model_has_permission(app, owner_user, barista_user, staff_user):
    """Permission checks should match ROLE_PERMISSIONS mapping."""
    with app.app_context():
        # Owner has all permissions
        assert owner_user.has_permission("users.view") is True
        assert owner_user.has_permission("users.create") is True
        assert owner_user.has_permission("users.deactivate") is True

        # Barista has dashboard.view only
        assert barista_user.has_permission("dashboard.view") is True
        assert barista_user.has_permission("users.view") is False
        assert barista_user.has_permission("users.create") is False

        # Staff has dashboard.view only
        assert staff_user.has_permission("dashboard.view") is True
        assert staff_user.has_permission("users.view") is False


def test_user_service_create_user(app, owner_user):
    """UserService.create_user should provision a new account."""
    with app.app_context():
        new_user = UserService.create_user(
            username="newstaff",
            email="newstaff@test.local",
            first_name="New",
            last_name="Staff",
            password="StaffPass123!",
            role=Roles.STAFF,
            is_active=True,
            actor=owner_user,
            ip_address="127.0.0.1"
        )
        assert new_user.id is not None
        assert new_user.username == "newstaff"
        assert new_user.role == Roles.STAFF
        assert new_user.is_active is True
        assert new_user.check_password("StaffPass123!") is True


def test_user_service_prevent_duplicate_username(app, owner_user):
    """Creating a user with an existing username should raise an error."""
    with app.app_context():
        with pytest.raises(AppException):
            UserService.create_user(
                username="test_owner",
                email="duplicate@test.local",
                first_name="Dup",
                last_name="User",
                password="DupPass123!",
                role=Roles.STAFF,
                is_active=True,
                actor=owner_user,
                ip_address="127.0.0.1"
            )


def test_user_service_privilege_escalation_guard(app, manager_user):
    """Manager should not be allowed to create an Owner account."""
    with app.app_context():
        with pytest.raises(AppException):
            UserService.create_user(
                username="sneaky_owner",
                email="sneaky@test.local",
                first_name="Sneaky",
                last_name="Owner",
                password="SneakyPass123!",
                role=Roles.OWNER,
                is_active=True,
                actor=manager_user,
                ip_address="127.0.0.1"
            )


def test_user_service_toggle_status(app, owner_user, barista_user):
    """Toggle status should deactivate/reactivate accounts."""
    with app.app_context():
        # Deactivate barista
        result = UserService.toggle_user_status(barista_user.id, actor=owner_user, ip_address="127.0.0.1")
        assert result.is_active is False

        # Reactivate barista
        result = UserService.toggle_user_status(barista_user.id, actor=owner_user, ip_address="127.0.0.1")
        assert result.is_active is True


def test_user_service_all_five_roles_exist(app):
    """Verify all 5 standard roles are defined."""
    with app.app_context():
        assert Roles.OWNER in Roles.ALL
        assert Roles.MANAGER in Roles.ALL
        assert Roles.CASHIER in Roles.ALL
        assert Roles.BARISTA in Roles.ALL
        assert Roles.STAFF in Roles.ALL
        assert len(Roles.ALL) == 5
