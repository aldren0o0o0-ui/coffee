from app.extensions import db
from app.modules.settings.models import StoreSetting


DEFAULT_SETTINGS = {
    "store_name": "John Coffee",
    "currency_symbol": "₱",
    "tax_rate": "0.08",
    "receipt_header": "Welcome to John Coffee Roasters!\nCraft Coffee & Fresh Pastries",
    "receipt_footer": "Thank you for supporting local coffee!\nHave a wonderful day!",
    "low_stock_threshold": "10.0"
}


class SettingsService:
    @staticmethod
    def get_setting(key, default=None):
        setting = StoreSetting.query.filter_by(key=key).first()
        if setting:
            return setting.value
        return DEFAULT_SETTINGS.get(key, default)

    @staticmethod
    def set_setting(key, value, description=None):
        setting = StoreSetting.query.filter_by(key=key).first()
        if not setting:
            setting = StoreSetting(key=key, value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.value = str(value)
            if description:
                setting.description = description
        db.session.commit()
        return setting

    @staticmethod
    def get_all_settings():
        settings = {k: v for k, v in DEFAULT_SETTINGS.items()}
        for s in StoreSetting.query.all():
            settings[s.key] = s.value
        return settings
