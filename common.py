from flask import jsonify, request

try:
    from .database import query
except ImportError:
    from database import query

def ingredient_record(row):
    on_hand = float(row.get("on_hand") or row.get("stock_quantity") or 0)
    reorder_level = float(row.get("reorder_level") or 0)
    return {
        "id": row.get("id") or row.get("ingredient_id"),
        "name": row.get("name") or row.get("ingredient_name"),
        "category": row.get("category") or "Other",
        "on_hand": on_hand,
        "unit": row.get("unit") or "pc",
        "reorder_level": reorder_level,
        "supplier": row.get("supplier") or "",
        "location": row.get("location") or "",
        "last_restocked": row.get("last_restocked") or "",
        "expiry_date": row.get("expiry_date") or "",
        "status": row.get("status") or ("Low Stock" if on_hand < reorder_level else "In Stock"),
    }

def validate_json(fields):
    body = request.get_json(silent=True)
    if body is None:
        body = request.form.to_dict()
    if not body:
        return None, (jsonify(error="Request body is empty. Please fill in all fields."), 400)
    missing = [field for field in fields if body.get(field) is None or not str(body.get(field)).strip()]
    if missing:
        return None, (jsonify(error=f"Missing fields: {', '.join(missing)}"), 400)
    return body, None

def manager_required():
    user_id = request.headers.get("X-User-Id")
    if not user_id or not user_id.isdigit():
        return jsonify(error="Manager authentication required"), 401
    users = query(
        "SELECT user_id, role FROM users WHERE user_id = %s AND is_active = TRUE",
        (int(user_id),),
    )
    if not users or users[0]["role"] not in ("Admin", "Manager"):
        return jsonify(error="Manager access required"), 403
    return None

def cashier_required():
    user_id = request.headers.get("X-User-Id")
    if not user_id or not user_id.isdigit():
        return jsonify(error="Cashier authentication required"), 401
    users = query(
        "SELECT user_id, role FROM users WHERE user_id = %s AND is_active = TRUE",
        (int(user_id),),
    )
    if not users or users[0]["role"] != "Cashier":
        return jsonify(error="Cashier access required"), 403
    return None

def order_status_update_required():
    user_id = request.headers.get("X-User-Id")
    if not user_id or not user_id.isdigit():
        return jsonify(error="Authentication required"), 401
    users = query(
        "SELECT user_id, role FROM users WHERE user_id = %s AND is_active = TRUE",
        (int(user_id),),
    )
    if not users:
        return jsonify(error="Authentication required"), 401
    if users[0]["role"] not in ("Admin", "Cashier"):
        return jsonify(error="You are not allowed to change order status"), 403
    return None

def product_response(row):
    row["price"] = f"₱{float(row['price']):,.0f}"
    row["emoji"] = row.get("emoji") or ("☕" if row["category"].lower() == "coffee" else "🍰")
    row["image"] = row.get("image") or ("coffee" if row["category"].lower() == "coffee" else "pastry")
    return row
