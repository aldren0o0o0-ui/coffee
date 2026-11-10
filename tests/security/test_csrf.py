from app import create_app
from app.extensions import db
from app.modules.users.models import User
from app.core.permissions import Roles


def test_csrf_protection_enabled_in_production():
    # Production app enforces CSRF
    prod_app = create_app("production")
    assert prod_app.config["WTF_CSRF_ENABLED"] is True

    # Testing app disables CSRF to allow automated testing fixtures
    test_app = create_app("testing")
    assert test_app.config["WTF_CSRF_ENABLED"] is False
