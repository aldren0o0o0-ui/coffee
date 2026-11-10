from app.extensions import limiter


def test_rate_limiter_initialized(app):
    assert limiter is not None
    assert app.config["RATELIMIT_STORAGE_URI"] == "memory://"
