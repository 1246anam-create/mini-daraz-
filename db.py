"""
Mini Daraz - Database Module
===========================
Handles SQLite database connection and schema.

The project uses SQLite (a file-based database) so it runs out of the box
with no external database server required.
"""

import os
import sqlite3
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Load .env file (minimal parser; no external dependency required)
# ---------------------------------------------------------------------------
def _load_env(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except FileNotFoundError:
        pass

_load_env()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "mini_daraz.db"),
)

PLACEHOLDER = "?"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """Yield a database connection and always close it afterwards."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, params=None, one=False):
    """Run a SELECT query and return rows (list of dicts)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        rows = [dict(r) for r in rows]
        if one:
            return rows[0] if rows else None
        return rows


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and return the lastrowid."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   VARCHAR(120) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    phone       VARCHAR(30),
    password    VARCHAR(255) NOT NULL,
    address     TEXT,
    city        VARCHAR(100),
    postal_code VARCHAR(20),
    status      VARCHAR(20) DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   VARCHAR(120) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    image       VARCHAR(255),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    brand           VARCHAR(120),
    description     TEXT,
    specifications  TEXT,
    price           NUMERIC(12,2) NOT NULL,
    discount        NUMERIC(5,2) DEFAULT 0,
    stock           INTEGER DEFAULT 0,
    image           VARCHAR(255),
    rating          NUMERIC(3,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',
    is_flash_sale   BOOLEAN DEFAULT FALSE,
    is_new          BOOLEAN DEFAULT FALSE,
    is_best_seller  BOOLEAN DEFAULT FALSE,
    is_trending     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cart (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity    INTEGER DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS wishlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number    VARCHAR(30) NOT NULL UNIQUE,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    customer_name   VARCHAR(120) NOT NULL,
    phone           VARCHAR(30) NOT NULL,
    email           VARCHAR(120) NOT NULL,
    address         TEXT NOT NULL,
    city            VARCHAR(100) NOT NULL,
    postal_code     VARCHAR(20),
    payment_method  VARCHAR(50) DEFAULT 'Cash on Delivery',
    subtotal        NUMERIC(12,2) DEFAULT 0,
    delivery_charge NUMERIC(12,2) DEFAULT 0,
    discount        NUMERIC(12,2) DEFAULT 0,
    total           NUMERIC(12,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'Pending',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    product_name VARCHAR(200) NOT NULL,
    product_image VARCHAR(255),
    price       NUMERIC(12,2) NOT NULL,
    quantity    INTEGER NOT NULL,
    subtotal    NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS contact_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   VARCHAR(120) NOT NULL,
    email       VARCHAR(120) NOT NULL,
    phone       VARCHAR(30),
    subject     VARCHAR(200),
    message     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    """Create all tables."""
    with get_db() as conn:
        cur = conn.cursor()
        for statement in SCHEMA.split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)
        conn.commit()
