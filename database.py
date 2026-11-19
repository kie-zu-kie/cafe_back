import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

load_dotenv(Path(__file__).resolve().parent / ".env")


def initialize_database():
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8"))


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it in the environment or backend/.env file."
        )
    return psycopg2.connect(database_url)


def ensure_ingredients_table():
    query(
        """
        CREATE TABLE IF NOT EXISTS ingredients (
            ingredient_id SERIAL PRIMARY KEY,
            ingredient_name VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL,
            stock_quantity NUMERIC(12, 2) NOT NULL DEFAULT 0,
            unit VARCHAR(20) NOT NULL,
            reorder_level NUMERIC(12, 2) NOT NULL DEFAULT 0,
            supplier VARCHAR(100),
            location VARCHAR(50),
            last_restocked DATE DEFAULT CURRENT_DATE,
            expiry_date DATE,
            status VARCHAR(20) NOT NULL DEFAULT 'In Stock'
        )
        """,
        fetch=False,
    )


def ensure_product_image_column():
    query(
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT",
        fetch=False,
    )


def query(sql, params=(), fetch=True):
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()] if fetch else None


def ensure_bootstrap_manager():
    if query(
        "SELECT user_id FROM users WHERE role IN ('Admin', 'Manager') LIMIT 1"
    ):
        return

    required = (
        "BOOTSTRAP_MANAGER_USERNAME",
        "BOOTSTRAP_MANAGER_NAME",
        "BOOTSTRAP_MANAGER_EMAIL",
        "BOOTSTRAP_MANAGER_PASSWORD",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            "No manager account exists. Set these environment variables to "
            f"provision the initial manager: {names}."
        )

    username = os.environ["BOOTSTRAP_MANAGER_USERNAME"].strip().lower()
    full_name = os.environ["BOOTSTRAP_MANAGER_NAME"].strip()
    email = os.environ["BOOTSTRAP_MANAGER_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_MANAGER_PASSWORD"]
    if len(password) < 12:
        raise RuntimeError(
            "BOOTSTRAP_MANAGER_PASSWORD must be at least 12 characters."
        )

    try:
        query(
            """
            INSERT INTO users (username, password_hash, full_name, email, role, is_active)
            VALUES (%s, %s, %s, %s, 'Manager', TRUE)
            """,
            (username, generate_password_hash(password), full_name, email),
            fetch=False,
        )
    except psycopg2.errors.UniqueViolation as error:
        raise RuntimeError(
            "Could not provision the initial manager because the username or email "
            "is already in use."
        ) from error
