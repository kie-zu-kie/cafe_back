from datetime import datetime

from flask import Blueprint, jsonify
from psycopg2.extras import RealDictCursor

try:
    from ..common import cashier_required, order_status_update_required, validate_json
    from ..database import get_connection, query
except ImportError:
    from common import cashier_required, order_status_update_required, validate_json
    from database import get_connection, query

bp = Blueprint("orders", __name__)

@bp.get("/api/orders")
def orders():
    rows = query(
        """
        SELECT o.order_id AS id, COALESCE(c.full_name, 'Walk-in customer') AS customer,
               o.order_date, o.total_amount AS total, o.status,
               COALESCE(json_agg(json_build_object(
                   'name', p.product_name, 'quantity', oi.quantity, 'price', oi.unit_price,
                   'image_url', p.image_url,
                   'emoji', CASE WHEN LOWER(p.category) = 'coffee' THEN '☕' ELSE '🍰' END
               ) ORDER BY oi.order_item_id) FILTER (WHERE oi.order_item_id IS NOT NULL), '[]') AS items
        FROM orders o
        LEFT JOIN customers c ON c.customer_id = o.customer_id
        LEFT JOIN order_items oi ON oi.order_id = o.order_id
        LEFT JOIN products p ON p.product_id = oi.product_id
        GROUP BY o.order_id, c.full_name
        ORDER BY o.order_date DESC NULLS LAST, o.order_id DESC
        """
    )
    result = []
    for row in rows:
        result.append({
            "id": f"#{row['id']}",
            "customer": row["customer"],
            "items": ", ".join(f"{item['name']} × {item['quantity']}" for item in row["items"]),
            "item_details": row["items"],
            "date": row["order_date"].strftime("%b %d, %I:%M %p") if row["order_date"] else "",
            "total": f"₱{float(row['total']):,.0f}",
            "status": row["status"] or "Pending",
            "className": {"Completed": "completed", "In progress": "progress"}.get(row["status"], "pending"),
        })
    return jsonify(result)

@bp.post("/api/orders")
def create_order():
    error = cashier_required()
    if error:
        return error
    body, error = validate_json(("customer", "items", "pickup_at", "total"))
    if error:
        return error
    try:
        pickup_at = datetime.fromisoformat(body["pickup_at"].replace("Z", "+00:00"))
    except ValueError:
        return jsonify(error="pickup_at must be an ISO date/time"), 400
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT customer_id FROM customers WHERE LOWER(full_name) = LOWER(%s) LIMIT 1",
                (body["customer"].strip(),),
            )
            customer = cursor.fetchone()
            customer_id = customer["customer_id"] if customer else None
            cursor.execute(
                "INSERT INTO orders (customer_id, order_date, total_amount, status, order_type) "
                "VALUES (%s, %s, %s, 'Pending', 'Takeout') RETURNING order_id",
                (customer_id, pickup_at, body["total"]),
            )
            order_id = cursor.fetchone()["order_id"]
            for item in body["items"]:
                cursor.execute(
                    "SELECT product_id FROM products "
                    "WHERE LOWER(product_name) = LOWER(%s) AND is_available = TRUE LIMIT 1",
                    (item["name"],),
                )
                product = cursor.fetchone()
                if not product:
                    return jsonify(error=f"Product not found: {item['name']}"), 400
                quantity = int(item["quantity"])
                price = float(item["price"])
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (order_id, product["product_id"], quantity, price, quantity * price),
                )
                cursor.execute(
                    "UPDATE inventory SET stock_quantity = GREATEST(0, stock_quantity - %s), "
                    "status = CASE WHEN GREATEST(0, stock_quantity - %s) < reorder_level "
                    "THEN 'Low Stock' ELSE 'In Stock' END WHERE product_id = %s",
                    (quantity, quantity, product["product_id"]),
                )
            if customer_id:
                cursor.execute(
                    "UPDATE customers SET total_orders = COALESCE(total_orders, 0) + 1, "
                    "total_spent = COALESCE(total_spent, 0) + %s WHERE customer_id = %s",
                    (body["total"], customer_id),
                )
    return jsonify(id=f"#{order_id}"), 201

@bp.patch("/api/orders/<int:order_id>")
def update_order(order_id):
    error = order_status_update_required()
    if error:
        return error
    body, error = validate_json(("status",))
    if error:
        return error
    rows = query(
        "UPDATE orders SET status = %s WHERE order_id = %s RETURNING order_id",
        (body["status"], order_id),
    )
    if not rows:
        return jsonify(error="Order not found"), 404
    return jsonify(success=True)
