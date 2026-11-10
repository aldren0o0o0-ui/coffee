from werkzeug.security import check_password_hash
from app.modules.users.models import User
from app.core.permissions import Roles


def test_password_hashing_security(app):
    with app.app_context():
        user = User(
            username="security_test",
            email="sec@test.local",
            first_name="Sec",
            last_name="User",
            role=Roles.BARISTA
        )
        raw_password = "SecretPassword123!"
        user.set_password(raw_password)

        # Ensure plaintext is never stored
        assert user.password_hash != raw_password
        assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")

        # Verify validation
        assert user.check_password(raw_password) is True
        assert user.check_password("WrongPassword123!") is False
