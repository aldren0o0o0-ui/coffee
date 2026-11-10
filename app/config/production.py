import os
from app.config import BaseConfig


def _get_database_uri():
    uri = os.environ.get("DATABASE_URL")
    if uri:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
        elif uri.startswith("postgresql://") and not uri.startswith("postgresql+"):
            uri = uri.replace("postgresql://", "postgresql+psycopg2://", 1)
    return uri


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _get_database_uri()
    
    # Production security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
