import os
from werkzeug.middleware.proxy_fix import ProxyFix
from app import create_app

# WSGI application callable for production servers (Gunicorn, Waitress, etc.)
flask_app = create_app(os.environ.get("FLASK_ENV", "production"))

# Trust 1 proxy layer (Render / Cloudflare / Nginx reverse proxy)
application = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if __name__ == "__main__":
    flask_app.run()
