import os
from app.config import BaseConfig


def _get_database_uri():
    uri = os.environ.get("DATABASE_URL")
    if uri and uri.startswith("postgres://"):
        # Fix Render/Heroku legacy postgres:// prefix for SQLAlchemy >= 1.4
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _get_database_uri()
    
    # Production security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
