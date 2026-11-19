import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

try:
    from .database import (
        ensure_bootstrap_manager,
        ensure_ingredients_table,
        ensure_product_image_column,
        initialize_database,
    )
except ImportError:
    from database import (
        ensure_bootstrap_manager,
        ensure_ingredients_table,
        ensure_product_image_column,
        initialize_database,
    )

load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

if os.getenv("DATABASE_URL"):
    initialize_database()
    ensure_ingredients_table()
    ensure_product_image_column()
    ensure_bootstrap_manager()


@app.after_request
def allow_frontend_origin(response):
    if request.path.startswith("/api/"):
        request_origin = request.headers.get("Origin")
        configured = os.getenv(
            "FRONTEND_ORIGIN",
            "http://127.0.0.1:8000",
        )
        allowed_origins = {"https://cafe-front-ten.vercel.app"} | {
            origin.strip().rstrip("/")
            for origin in configured.split(",")
            if origin.strip()
        }
        if request_origin and request_origin.rstrip("/") in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Id"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    return response


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify(error="Uploads must be 5 MB or smaller"), 413


try:
    from .routes.analytics import bp as analytics_bp
    from .routes.auth import bp as auth_bp
    from .routes.catalog import bp as catalog_bp
    from .routes.inventory import bp as inventory_bp
    from .routes.orders import bp as orders_bp
except ImportError:
    from routes.analytics import bp as analytics_bp
    from routes.auth import bp as auth_bp
    from routes.catalog import bp as catalog_bp
    from routes.inventory import bp as inventory_bp
    from routes.orders import bp as orders_bp

for blueprint in (auth_bp, catalog_bp, inventory_bp, orders_bp, analytics_bp):
    app.register_blueprint(blueprint)
