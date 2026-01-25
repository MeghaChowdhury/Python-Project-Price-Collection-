import re
import pandas as pd
import mysql.connector
from datetime import date

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Megha616@",
    "port": 3306,
    "database": "price_collection",
}

PRICE_TABLE = "PRICE"
SELLER_OUR = "Our company"


def parse_price(value):
    """Convert '839,99', '1.299,99 €', 839.99 -> float or None."""
    if value is None:
        return None

    t = str(value).replace("\xa0", " ").strip()
    if not t:
        return None

    m = re.search(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2}|\d+)", t)
    if not m:
        return None

    num = m.group(0)
    if "." in num and "," in num:
        num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        num = num.replace(",", ".")

    try:
        return float(num)
    except ValueError:
        return None


def find_col(df, *candidates):
    """Find column by case-insensitive match."""
    norm = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    return None


def run_our_company_today(excel_path="products.xlsx"):
    today = date.today()

    df = pd.read_excel(excel_path).fillna("")
    product_col = find_col(df, "Product name", "product_name", "product", "name")
    price_col = find_col(df, "Our company price", "our_company_price", "Our Company Price", "our price", "Our price")

    if not product_col or not price_col:
        raise ValueError(
            f"Missing columns in {excel_path}. Found: {list(df.columns)}\n"
            f"Need product + our company price columns."
        )

    rows = []
    for _, row in df.iterrows():
        product = str(row[product_col]).strip()
        price_val = parse_price(row[price_col])

        if not product:
            continue
        if price_val is None:
            print(f"[WARN] Skipping {product} (invalid Our company price: {row[price_col]})")
            continue

        rows.append((product, today, SELLER_OUR, round(price_val, 2)))
        print(f"[OK] {product} | {SELLER_OUR}: {price_val:.2f} €")

    if not rows:
        print("[WARN] No rows to insert.")
        return

    sql = f"""
    INSERT INTO {PRICE_TABLE} (Product, Date, Seller, Price)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE Price = VALUES(Price);
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()

    print(f"\n[DB] Inserted/updated {len(rows)} rows into {DB_CONFIG['database']}.{PRICE_TABLE} for {today.isoformat()}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    run_our_company_today("products.xlsx")
