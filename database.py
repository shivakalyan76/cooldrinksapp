import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'shop.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL UNIQUE,
            price   REAL    NOT NULL,
            stock   INTEGER NOT NULL DEFAULT 0
        );

       CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    customer_name TEXT,
    customer_mobile TEXT,
    total REAL NOT NULL
);

        CREATE TABLE IF NOT EXISTS bill_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id     INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            quantity    INTEGER NOT NULL,
            subtotal    REAL    NOT NULL,
            FOREIGN KEY (bill_id)    REFERENCES bills(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    ''')

    conn.commit()
    conn.close()
