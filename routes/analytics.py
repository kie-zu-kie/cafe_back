from flask import Blueprint, jsonify, request

try:
    from ..database import query
except ImportError:
    from database import query

bp = Blueprint("analytics", __name__)

@bp.get("/api/health")
def health():
    query("SELECT 1")
    return jsonify(status="ok", database="je_cafe_db")

@bp.get("/api/dashboard")
def dashboard():
    period = request.args.get("period", "7d")
    if period not in ("7d", "month"):
        return jsonify(error="period must be '7d' or 'month'"), 400

    summary = query(
        """
        SELECT COALESCE(SUM(total_amount) FILTER (WHERE order_date::date = CURRENT_DATE), 0)::float AS sales_today,
               COUNT(*) FILTER (WHERE order_date::date = CURRENT_DATE)::int AS orders_today,
               COALESCE(AVG(total_amount) FILTER (WHERE order_date::date = CURRENT_DATE), 0)::float AS average_order,
               COALESCE(SUM(total_amount) FILTER (
                   WHERE order_date::date BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE
               ), 0)::float AS week_sales
        FROM orders
        """
    )[0]
    inventory_summary = query(
        """
        SELECT COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE stock_quantity < reorder_level)::int AS low_stock
        FROM ingredients
        """
    )[0]
    top_products = query(
        """
        SELECT p.product_name AS name, p.category, p.unit,
               COALESCE(SUM(oi.quantity), 0)::int AS quantity,
               COALESCE(SUM(oi.subtotal), 0)::float AS sales
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.order_date::date BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE
        GROUP BY p.product_id
        ORDER BY sales DESC
        LIMIT 4
        """
    )
    sales_by_day = query(
        """
        SELECT TO_CHAR(day, 'Mon DD') AS label, COALESCE(SUM(o.total_amount), 0)::float AS sales
        FROM generate_series(
            CASE WHEN %s = 'month'
                 THEN date_trunc('month', CURRENT_DATE)::date
                 ELSE CURRENT_DATE - 6 END,
            CURRENT_DATE,
            INTERVAL '1 day'
        ) day
        LEFT JOIN orders o ON o.order_date::date = day::date
        GROUP BY day ORDER BY day
        """,
        (period,),
    )
    schedule = query(
        """
        SELECT o.order_id AS id, COALESCE(c.full_name, 'Walk-in customer') AS customer,
               o.order_date, o.status,
               COALESCE(string_agg(
                   p.product_name || ' × ' || oi.quantity,
                   ', ' ORDER BY oi.order_item_id
               ), '') AS items
        FROM orders o
        LEFT JOIN customers c ON c.customer_id = o.customer_id
        LEFT JOIN order_items oi ON oi.order_id = o.order_id
        LEFT JOIN products p ON p.product_id = oi.product_id
        WHERE o.order_date::date = CURRENT_DATE
        GROUP BY o.order_id, c.full_name
        ORDER BY o.order_date LIMIT 5
        """
    )
    for item in schedule:
        item["time"] = item["order_date"].strftime("%H:%M")
    return jsonify({
        **summary,
        "low_stock": inventory_summary["low_stock"],
        "inventory_total": inventory_summary["total"],
        "period": period,
        "top_products": top_products,
        "sales_by_day": sales_by_day,
        "schedule": schedule,
    })

@bp.get("/api/reports")
def reports():
    summary = query(
        """
        SELECT COALESCE(SUM(total_amount), 0)::float AS gross_revenue,
               COUNT(*)::int AS total_orders
        FROM orders
        """
    )[0]
    best = query(
        """
        SELECT p.product_name AS name, COALESCE(SUM(oi.quantity), 0)::int AS quantity
        FROM order_items oi JOIN products p ON p.product_id = oi.product_id
        GROUP BY p.product_id ORDER BY quantity DESC LIMIT 1
        """
    )
    return jsonify({
        **summary,
        "best_seller": best[0] if best else {"name": "No sales yet", "quantity": 0},
    })
