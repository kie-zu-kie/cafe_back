from flask import Blueprint, jsonify

try:
    from ..common import ingredient_record, validate_json
    from ..database import query
except ImportError:
    from common import ingredient_record, validate_json
    from database import query

bp = Blueprint("inventory", __name__)

@bp.get("/api/ingredients")
def ingredients():
    rows = query(
        """
        SELECT ingredient_id AS id, ingredient_name AS name, category,
               stock_quantity::float AS on_hand, unit,
               reorder_level::float AS reorder_level,
               supplier, location, last_restocked, expiry_date, status
        FROM ingredients
        ORDER BY ingredient_name
        """
    )
    return jsonify([ingredient_record(row) for row in rows])

@bp.post("/api/ingredients")
def create_ingredient():
    body, error = validate_json(("name", "category", "on_hand", "unit", "reorder_level", "supplier"))
    if error:
        return error
    name = body["name"].strip()
    category = body["category"].strip()
    on_hand = float(body["on_hand"])
    reorder_level = float(body["reorder_level"])
    unit = body["unit"].strip()
    supplier = body["supplier"].strip()
    rows = query(
        """
        INSERT INTO ingredients (
            ingredient_name, category, stock_quantity, unit, reorder_level, supplier,
            location, last_restocked, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s)
        RETURNING ingredient_id AS id, ingredient_name AS name, category,
                  stock_quantity::float AS on_hand, unit, reorder_level::float AS reorder_level,
                  supplier, location, last_restocked, status
        """,
        (
            name,
            category,
            on_hand,
            unit,
            reorder_level,
            supplier,
            body.get("location") or "",
            "Low Stock" if on_hand < reorder_level else "In Stock",
        ),
    )
    return jsonify(ingredient_record(rows[0])), 201

@bp.patch("/api/ingredients/<int:ingredient_id>")
def update_ingredient(ingredient_id):
    body, error = validate_json(("name", "category", "on_hand", "unit", "reorder_level", "supplier"))
    if error:
        return error
    on_hand = float(body["on_hand"])
    reorder_level = float(body["reorder_level"])
    rows = query(
        """
        UPDATE ingredients
        SET ingredient_name = %s,
            category = %s,
            stock_quantity = %s,
            unit = %s,
            reorder_level = %s,
            supplier = %s,
            status = %s
        WHERE ingredient_id = %s
        RETURNING ingredient_id AS id, ingredient_name AS name, category,
                  stock_quantity::float AS on_hand, unit, reorder_level::float AS reorder_level,
                  supplier, location, last_restocked, expiry_date, status
        """,
        (
            body["name"].strip(),
            body["category"].strip(),
            on_hand,
            body["unit"].strip(),
            reorder_level,
            body["supplier"].strip(),
            "Low Stock" if on_hand < reorder_level else "In Stock",
            ingredient_id,
        ),
    )
    if not rows:
        return jsonify(error="Ingredient not found"), 404
    return jsonify(ingredient_record(rows[0]))

@bp.get("/api/inventory")
def inventory():
    return ingredients()

@bp.post("/api/inventory")
def create_inventory():
    return create_ingredient()
