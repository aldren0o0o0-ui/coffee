import os
from app.config import BaseConfig, BASE_DIR


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    
    # Priority: DATABASE_URL from .env, else fallback to instance SQLite
    default_sqlite = f"sqlite:///{BASE_DIR / 'instance' / 'coffee_dev.db'}"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or default_sqlite
    
    # Enable query echoing if requested
    SQLALCHEMY_ECHO = os.environ.get("SQLALCHEMY_ECHO", "False").lower() in ("true", "1")
