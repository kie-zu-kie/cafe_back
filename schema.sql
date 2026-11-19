CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    join_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_spent NUMERIC(12, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    sku VARCHAR(50) UNIQUE,
    price NUMERIC(12, 2) NOT NULL,
    cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
    unit VARCHAR(20) NOT NULL DEFAULT 'pc',
    description TEXT,
    image_url TEXT,
    is_available BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS product_images (
    product_id INTEGER PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
    mime_type VARCHAR(30) NOT NULL,
    image_data BYTEA NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id INTEGER UNIQUE REFERENCES products(product_id) ON DELETE CASCADE,
    stock_quantity NUMERIC(12, 2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(12, 2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'In Stock'
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    order_type VARCHAR(30) NOT NULL DEFAULT 'Takeout'
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL
);

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
);

CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_products_available ON products(is_available);
