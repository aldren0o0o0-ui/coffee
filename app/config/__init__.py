import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "coffee-shop-sme-default-super-secret-key-321")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_SESSION_OPTIONS = {"expire_on_commit": False}
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Application details
    APP_NAME = "Coffee Shop SME"
    STORE_NAME = os.environ.get("STORE_NAME", "John Coffee")
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "$")
    TAX_RATE = float(os.environ.get("DEFAULT_TAX_RATE", 0.08))  # 8% default sales tax

    # Rate Limiting
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per day;50 per hour")
    RATELIMIT_STORAGE_URI = "memory://"


from app.config.development import DevelopmentConfig
from app.config.testing import TestingConfig
from app.config.production import ProductionConfig

config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
