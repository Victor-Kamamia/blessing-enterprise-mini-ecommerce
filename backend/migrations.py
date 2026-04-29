from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        source TEXT NOT NULL,
        currency TEXT NOT NULL,
        total_amount REAL NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT NOT NULL DEFAULT '',
        customer_address TEXT NOT NULL,
        whatsapp_message TEXT NOT NULL DEFAULT '',
        whatsapp_url TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        delivery_status TEXT NOT NULL DEFAULT 'new',
        delivery_updated_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_reference TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        image TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(order_reference) REFERENCES orders(reference) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_reference TEXT NOT NULL,
        provider TEXT NOT NULL,
        provider_mode TEXT NOT NULL,
        status TEXT NOT NULL,
        amount REAL NOT NULL,
        phone_number TEXT NOT NULL,
        merchant_request_id TEXT NOT NULL DEFAULT '',
        checkout_request_id TEXT NOT NULL DEFAULT '',
        mpesa_receipt_number TEXT NOT NULL DEFAULT '',
        result_code INTEGER,
        result_desc TEXT NOT NULL DEFAULT '',
        paid_at TEXT NOT NULL DEFAULT '',
        request_payload TEXT NOT NULL DEFAULT '{}',
        response_payload TEXT NOT NULL DEFAULT '{}',
        raw_callback_payload TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(order_reference) REFERENCES orders(reference) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS email_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_reference TEXT NOT NULL,
        event_type TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT NOT NULL DEFAULT '',
        payload_snapshot TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(order_reference) REFERENCES orders(reference) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_orders_reference ON orders(reference)",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_orders_payment_status ON orders(payment_status)",
    "CREATE INDEX IF NOT EXISTS idx_orders_delivery_status ON orders(delivery_status)",
    "CREATE INDEX IF NOT EXISTS idx_order_items_reference ON order_items(order_reference)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_reference ON transactions(order_reference)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_checkout_request ON transactions(checkout_request_id)",
    "CREATE INDEX IF NOT EXISTS idx_email_notifications_reference ON email_notifications(order_reference)",
]


def run_migrations(connection: sqlite3.Connection) -> None:
    with connection:
        schema_prefix = SCHEMA_STATEMENTS[:4]
        schema_suffix = SCHEMA_STATEMENTS[4:]
        for statement in schema_prefix:
            connection.execute(statement)
        _ensure_orders_delivery_columns(connection)
        for statement in schema_suffix:
            connection.execute(statement)


def _ensure_orders_delivery_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(orders)").fetchall()}
    if "delivery_status" not in existing_columns:
        connection.execute("ALTER TABLE orders ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'new'")
    if "delivery_updated_at" not in existing_columns:
        connection.execute("ALTER TABLE orders ADD COLUMN delivery_updated_at TEXT NOT NULL DEFAULT ''")
