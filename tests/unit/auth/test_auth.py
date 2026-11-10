import pytest
from app.modules.auth.services import AuthService
from app.modules.users.models import User
from app.core.exceptions import UnauthorizedError


def test_auth_authenticate_success(app, owner_user):
    with app.app_context():
        user = AuthService.authenticate("test_owner", "Owner123!")
        assert user is not None
        assert user.username == "test_owner"
        assert user.last_login_at is not None


def test_auth_authenticate_invalid_password(app, owner_user):
    with app.app_context():
        with pytest.raises(UnauthorizedError):
            AuthService.authenticate("test_owner", "WrongPassword!")


def test_auth_authenticate_unknown_user(app):
    with app.app_context():
        with pytest.raises(UnauthorizedError):
            AuthService.authenticate("nonexistent", "SomePassword123!")
