"""Turns the raw store files into query-ready artifacts.

    python -m emporio.ingest

Outputs (in data/processed/):
    emporio.db       SQLite with clean tables, a `catalog` view and a full-text index
    data_quality.md  inconsistencies found in the raw data, kept for the README
"""

import csv
import json
import sqlite3

from emporio.config import DB_PATH, PROCESSED_DIR, RAW_DIR
from emporio.text import digits, normalize

SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories,
    description TEXT,
    price_brl REAL NOT NULL,
    stock_quantity INTEGER NOT NULL,
    status TEXT NOT NULL,           -- active | discontinued | coming_soon
    string_type TEXT,               -- nylon | aco | NULL (acoustic guitars and ukuleles only)
    electric INTEGER,               -- 1 when it has pickups/electronics, NULL when unknown
    color TEXT,
    specs_json TEXT,
    created_at TEXT
);

CREATE TABLE promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products,
    discount_percent REAL NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    phone_digits TEXT,
    email TEXT,
    city TEXT
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,           -- pending | confirmed | shipped | delivered | cancelled
    total_brl REAL NOT NULL,
    payment_method TEXT,
    tracking_code TEXT,
    estimated_delivery TEXT,
    notes TEXT
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders,
    product_id INTEGER NOT NULL REFERENCES products,
    quantity INTEGER NOT NULL
);

CREATE INDEX idx_products_category ON products(category_id, price_brl);
CREATE INDEX idx_promotions_product ON promotions(product_id, is_active);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- Everything the agent needs to quote a product, already computed.
-- Policy 6.2: promotions are not cumulative, so the 5% PIX discount only applies
-- when the product has no active promotion.
CREATE VIEW catalog AS
SELECT
    p.product_id,
    p.name,
    c.name AS category,
    p.category_id,
    p.description,
    p.string_type,
    p.electric,
    p.color,
    p.specs_json,
    p.stock_quantity,
    p.status,
    CASE
        WHEN p.status = 'discontinued' THEN 'descontinuado'
        WHEN p.status = 'coming_soon' THEN 'em breve'
        WHEN p.stock_quantity <= 0 THEN 'esgotado'
        ELSE 'disponivel'
    END AS availability,
    p.price_brl AS list_price,
    promo.discount_percent,
    promo.description AS promotion,
    ROUND(p.price_brl * (1 - COALESCE(promo.discount_percent, 0) / 100.0), 2) AS final_price,
    CASE WHEN promo.discount_percent IS NULL THEN ROUND(p.price_brl * 0.95, 2) END AS pix_price
FROM products p
JOIN categories c USING (category_id)
LEFT JOIN (
    -- if a product ever has two active promotions, the customer gets the larger one
    SELECT product_id, MAX(discount_percent) AS discount_percent, description
    FROM promotions
    WHERE is_active = 1
    GROUP BY product_id
) promo USING (product_id);

-- Accent-free full-text index. The name gets a higher weight in bm25 at query time.
CREATE VIRTUAL TABLE product_search USING fts5(
    product_id UNINDEXED,
    name,
    body,
    tokenize = 'unicode61'
);
"""


def read_csv(name: str) -> list[dict]:
    with open(RAW_DIR / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def string_type(specs: dict) -> str | None:
    value = normalize(specs.get("strings", ""))
    if value == "nylon":
        return "nylon"
    if value in ("aco", "steel"):
        return "aco"
    return None


def electric(specs: dict) -> int | None:
    value = normalize(specs.get("electronics", ""))
    if not value:
        return None
    return 0 if value == "no" else 1


def build_database() -> sqlite3.Connection:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    categories = read_csv("categories.csv")
    conn.executemany(
        "INSERT INTO categories VALUES (?, ?, ?)",
        [(int(c["category_id"]), c["name"], c["description"]) for c in categories],
    )
    category_names = {int(c["category_id"]): c["name"] for c in categories}

    for p in read_csv("products.csv"):
        specs = json.loads(p["specs"] or "{}")
        product_id = int(p["product_id"])
        conn.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                product_id,
                p["name"].strip(),
                int(p["category_id"]),
                p["description"],
                float(p["price_brl"]),
                int(p["stock_quantity"]),
                p["status"],
                string_type(specs),
                electric(specs),
                specs.get("color"),
                json.dumps(specs, ensure_ascii=False),
                p["created_at"],
            ),
        )
        body = " ".join(
            [category_names[int(p["category_id"])], p["description"], *map(str, specs.values())]
        )
        conn.execute(
            "INSERT INTO product_search VALUES (?, ?, ?)",
            (product_id, normalize(p["name"]), normalize(body)),
        )

    conn.executemany(
        "INSERT INTO promotions VALUES (?, ?, ?, ?, ?)",
        [
            (
                int(r["promotion_id"]),
                int(r["product_id"]),
                float(r["discount_percent"]),
                r["description"],
                int(r["is_active"]),
            )
            for r in read_csv("promotions.csv")
        ],
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                int(r["customer_id"]),
                r["name"],
                r["phone"],
                digits(r["phone"]),
                r["email"].strip().lower(),
                r["city"],
            )
            for r in read_csv("customers.csv")
        ],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                int(r["order_id"]),
                int(r["customer_id"]),
                r["order_date"],
                r["status"],
                float(r["total_brl"]),
                r["payment_method"] or None,
                r["tracking_code"] or None,
                r["estimated_delivery"] or None,
                r["notes"] or None,
            )
            for r in read_csv("orders.csv")
        ],
    )
    conn.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?)",
        [
            (int(r["order_id"]), int(r["product_id"]), int(r["quantity"]))
            for r in read_csv("order_items.csv")
        ],
    )
    conn.commit()
    return conn


def data_quality_report(conn: sqlite3.Connection) -> list[str]:
    """Inconsistencies the agent has to live with. Reported, never silently fixed."""
    issues = []

    for order_id, total, items_sum in conn.execute(
        """
        SELECT o.order_id, o.total_brl, SUM(oi.quantity * p.price_brl)
        FROM orders o
        JOIN order_items oi USING (order_id)
        JOIN products p USING (product_id)
        GROUP BY o.order_id
        HAVING ABS(o.total_brl - SUM(oi.quantity * p.price_brl)) > 0.01
        """
    ):
        issues.append(
            f"Order {order_id}: total is {total:.2f} but its items add up to "
            f"{items_sum:.2f} at current list prices (could be a past price or discount)."
        )

    for order_id, status, product_id, product_status in conn.execute(
        """
        SELECT o.order_id, o.status, p.product_id, p.status
        FROM orders o
        JOIN order_items oi USING (order_id)
        JOIN products p USING (product_id)
        WHERE p.status = 'coming_soon' AND o.status = 'delivered'
        """
    ):
        issues.append(
            f"Order {order_id} is {status} but contains product {product_id}, "
            f"which is {product_status}."
        )

    for (category,) in conn.execute(
        """
        SELECT c.name FROM categories c
        LEFT JOIN products p USING (category_id)
        WHERE p.product_id IS NULL
        """
    ):
        issues.append(f"Category '{category}' has no products.")

    for product_id, n in conn.execute(
        "SELECT product_id, COUNT(*) FROM promotions GROUP BY product_id HAVING COUNT(*) > 1"
    ):
        issues.append(f"Product {product_id} has {n} promotions on record (none active at once).")

    for order_id, status, eta in conn.execute(
        """
        SELECT order_id, status, estimated_delivery FROM orders
        WHERE status = 'shipped' AND estimated_delivery < date('now')
        """
    ):
        issues.append(f"Order {order_id} is still '{status}' although delivery was due {eta}.")

    return issues


def main() -> None:
    conn = build_database()
    issues = data_quality_report(conn)
    report = "# Data quality report\n\nGenerated by `python -m emporio.ingest`.\n\n"
    report += "\n".join(f"* {line}" for line in issues) + "\n"
    (PROCESSED_DIR / "data_quality.md").write_text(report, encoding="utf-8")

    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("products", "categories", "promotions", "customers", "orders", "order_items")
    }
    print(f"Database written to {DB_PATH}: {counts}")
    print(f"{len(issues)} data quality issues, see data/processed/data_quality.md")


if __name__ == "__main__":
    main()
