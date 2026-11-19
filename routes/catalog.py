import os
from uuid import uuid4

import psycopg2
from flask import Blueprint, current_app, jsonify, request

try:
    from ..common import manager_required, product_response, validate_json
    from ..database import query
except ImportError:
    from common import manager_required, product_response, validate_json
    from database import query

bp = Blueprint("catalog", __name__)
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
}
IMAGE_SIGNATURES = {
    "jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}


@bp.get("/api/products")
def products():
    rows = query(
        "SELECT product_id AS id, product_name AS name, COALESCE(description, '') AS description, "
        "price, category, unit, image_url FROM products WHERE is_available = TRUE "
        "ORDER BY category, product_name"
    )
    return jsonify([product_response(row) for row in rows])

@bp.post("/api/products")
def create_product():
    error = manager_required()
    if error:
        return error
    body, error = validate_json(("name", "description", "price", "category"))
    if error:
        return error
    name = body["name"].strip()
    category = body["category"].strip().lower()
    unit = body.get("unit", "pc")
    sku = body.get("sku") or f"JE-{name.upper().replace(' ', '-')[:20]}"
    try:
        rows = query(
            "INSERT INTO products (product_name, category, sku, price, cost, unit, description) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "RETURNING product_id AS id, product_name AS name, description, price, category, unit, image_url",
            (name, category, sku, body["price"], body.get("cost", body["price"]), unit, body["description"].strip()),
        )
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="A product with that name or SKU already exists"), 409
    return jsonify(product_response(rows[0])), 201

@bp.patch("/api/products/<int:product_id>")
def update_product(product_id):
    error = manager_required()
    if error:
        return error
    body, error = validate_json(("price",))
    if error:
        return error
    rows = query(
        "UPDATE products SET price = %s WHERE product_id = %s "
        "RETURNING product_id AS id, product_name AS name, description, price, category, unit, image_url",
        (body["price"], product_id),
    )
    if not rows:
        return jsonify(error="Product not found"), 404
    return jsonify(product_response(rows[0]))


@bp.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    error = manager_required()
    if error:
        return error
    rows = query(
        "UPDATE products SET is_available = FALSE "
        "WHERE product_id = %s AND is_available = TRUE RETURNING product_id",
        (product_id,),
    )
    if not rows:
        return jsonify(error="Product not found"), 404
    return "", 204


@bp.post("/api/products/<int:product_id>/image")
def upload_product_image(product_id):
    error = manager_required()
    if error:
        return error

    image = request.files.get("image")
    if not image or not image.filename:
        return jsonify(error="Choose a product image to upload"), 400

    extension = os.path.splitext(image.filename)[1].lower()
    image_type = ALLOWED_IMAGE_EXTENSIONS.get(extension)
    if not image_type:
        return jsonify(error="Use a JPG, PNG, or WebP image"), 400

    signature = image.stream.read(12)
    image.stream.seek(0)
    if not IMAGE_SIGNATURES[image_type](signature):
        return jsonify(error="The uploaded file is not a valid image"), 400

    rows = query(
        "SELECT image_url FROM products WHERE product_id = %s",
        (product_id,),
    )
    if not rows:
        return jsonify(error="Product not found"), 404

    upload_folder = os.path.join(current_app.static_folder, "uploads", "products")
    os.makedirs(upload_folder, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    image_path = os.path.join(upload_folder, filename)
    public_backend_url = (
        os.getenv("PUBLIC_BACKEND_URL", "").strip().rstrip("/")
        or request.host_url.rstrip("/")
    )
    image_url = f"{public_backend_url}/static/uploads/products/{filename}"
    image.save(image_path)

    try:
        updated = query(
            "UPDATE products SET image_url = %s WHERE product_id = %s "
            "RETURNING product_id AS id, product_name AS name, description, price, category, unit, image_url",
            (image_url, product_id),
        )
    except psycopg2.Error:
        os.remove(image_path)
        raise
    if not updated:
        os.remove(image_path)
        return jsonify(error="Product not found"), 404

    previous_url = rows[0].get("image_url")
    if previous_url and previous_url.startswith("/static/uploads/products/"):
        previous_path = os.path.join(upload_folder, os.path.basename(previous_url))
        if os.path.isfile(previous_path) and previous_path != image_path:
            os.remove(previous_path)

    return jsonify(product_response(updated[0]))


@bp.get("/api/customers")
def customers():
    rows = query(
        """
        SELECT c.customer_id AS id, c.full_name AS name,
               COALESCE(c.email, c.phone, '') AS contact,
               COALESCE(c.total_orders, 0) AS orders,
               COALESCE(c.total_spent, 0)::float AS value,
               COALESCE(TO_CHAR(MAX(o.order_date), 'Mon DD, YYYY'), 'No orders yet') AS last_order
        FROM customers c
        LEFT JOIN orders o ON o.customer_id = c.customer_id
        GROUP BY c.customer_id
        ORDER BY c.join_date DESC NULLS LAST, c.customer_id DESC
        """
    )
    return jsonify(rows)

@bp.post("/api/customers")
def create_customer():
    body, error = validate_json(("name", "contact"))
    if error:
        return error
    contact = body["contact"].strip()
    email = contact if "@" in contact else None
    phone = None if email else contact
    rows = query(
        "INSERT INTO customers (full_name, email, phone) VALUES (%s, %s, %s) "
        "RETURNING customer_id AS id, full_name AS name, COALESCE(email, phone, '') AS contact",
        (body["name"].strip(), email, phone),
    )
    return jsonify({**rows[0], "orders": 0, "value": 0, "last_order": "No orders yet"}), 201
