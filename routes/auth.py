from flask import Blueprint, jsonify, request
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from ..common import manager_required, validate_json
    from ..database import query
except ImportError:
    from common import manager_required, validate_json
    from database import query

bp = Blueprint("auth", __name__)

@bp.post("/api/login")
def login():
    body, error = validate_json(("identifier", "password"))
    if error:
        return error
    users = query(
        """
        SELECT user_id, username, password_hash, full_name, email, role
        FROM users
        WHERE is_active = TRUE AND (LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s))
        LIMIT 1
        """,
        (body["identifier"].strip(), body["identifier"].strip()),
    )
    if not users or not check_password_hash(users[0]["password_hash"], body["password"]):
        return jsonify(error="Invalid username/email or password"), 401
    user = users[0]
    query("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s", (user["user_id"],), fetch=False)
    return jsonify({
        "id": user["user_id"],
        "username": user["username"],
        "name": user["full_name"],
        "email": user["email"],
        "role": user["role"],
    })

@bp.get("/api/admin/users")
def admin_users():
    error = manager_required()
    if error:
        return error
    return jsonify(query(
        "SELECT user_id AS id, username, full_name AS name, email, role, is_active, last_login "
        "FROM users WHERE role = 'Cashier' ORDER BY full_name"
    ))

@bp.post("/api/admin/users")
def create_cashier():
    error = manager_required()
    if error:
        return error
    body, validation_error = validate_json(("username", "name", "email", "password"))
    if validation_error:
        return validation_error
    try:
        rows = query(
            "INSERT INTO users (username, password_hash, full_name, email, role, is_active) "
            "VALUES (%s, %s, %s, %s, 'Cashier', TRUE) "
            "RETURNING user_id AS id, username, full_name AS name, email, role, is_active",
            (
                body["username"].strip().lower(),
                generate_password_hash(body["password"]),
                body["name"].strip(),
                body["email"].strip().lower(),
            ),
        )
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="Username or email already exists"), 409
    return jsonify(rows[0]), 201

@bp.patch("/api/admin/users/<int:user_id>")
def update_cashier(user_id):
    error = manager_required()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    if body.get("is_active") is not None:
        rows = query(
            "UPDATE users SET is_active = %s WHERE user_id = %s AND role = 'Cashier' "
            "RETURNING user_id",
            (bool(body["is_active"]), user_id),
        )
    elif body.get("password"):
        rows = query(
            "UPDATE users SET password_hash = %s WHERE user_id = %s AND role = 'Cashier' "
            "RETURNING user_id",
            (generate_password_hash(body["password"]), user_id),
        )
    else:
        return jsonify(error="Provide is_active or password"), 400
    if not rows:
        return jsonify(error="Cashier not found"), 404
    return jsonify(success=True)
