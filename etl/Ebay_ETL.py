import re
import os
import time
import datetime as dt
import requests
import pandas as pd
from bs4 import BeautifulSoup
import mysql.connector

# CONFIG
HEADERS = { # makes the request look like a normal browser so eBay doesn’t block us.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

DB_CONFIG = { # credentials for MySQL.
    "host": "localhost",
    "user": "etl_user",
    "password": "Megha6162",     # <-- change before use
    "port": 3306,
    "database": "price_collection", #change according to the database name u have
}
#  PRICE_TABLE, SELLER_EBAY: standardizes seller name.
PRICE_TABLE = "PRICE"
SELLER_EBAY = "Ebay"

REQUEST_DELAY_SECONDS = 2.0 # delay so you don’t get rate-limited.

# HELPERS
def normalize_text(s: str) -> str: # Cleans strings: removes weird spaces and extra whitespace.
    if s is None:
        return ""
    return " ".join(str(s).replace("\xa0", " ").strip().split())


def parse_price_eur(text: str): # Handles European formatting, because it's better to save decimal values in the Database
    """
    Parses:
      - '1.299,99 €'  -> 1299.99
      - '899,99 €'    -> 899.99
      - '899.99 €'    -> 899.99
      - 'EUR 2.049,00'-> 2049.00
    """
    if not text:
        return None

    t = normalize_text(text)

    m = re.search(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})", t)
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


def shipping_cost(text: str) -> float: #to make sure we also include the shipping price
    """
    eBay DE examples:
      'Kostenloser Versand' -> 0
      '+EUR 4,99 Versand'   -> 4.99
    If unknown -> 0
    """
    if not text:
        return 0.0

    low = text.lower()
    if "kostenlos" in low or "gratis" in low:
        return 0.0

    p = parse_price_eur(text)
    return p if p is not None else 0.0

# EBAY SCRAPE
def scrape_ebay_price(url: str): # This is the core scraping function. It returns one final price (price + shipping).
    """
    Returns ONE price for the URL:
    - If listing page: take the first valid item's (price + shipping)
    - If item page: take that item's (price + shipping)
    """
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # ---------- CASE 1: LISTING PAGE ----------
    items = soup.select("li.s-item") # If it finds multiple items, it loops until it finds the first valid price and returns it.
    if items:
        for item in items:
            price_el = item.select_one(".s-item__price")
            ship_el = item.select_one(".s-item__shipping, .s-item__logisticsCost")

            price = parse_price_eur(price_el.get_text(" ", strip=True) if price_el else "")
            if price is None:
                continue

            ship = shipping_cost(ship_el.get_text(" ", strip=True) if ship_el else "")
            return round(price + ship, 2)

        return None

    # ---------- CASE 2: ITEM PAGE ----------
    price_candidates = [ # If no listing items, it assumes it’s an individual product page and tries multiple selectors to locate the price and shipping.
        "#prcIsum",
        "#mm-saleDscPrc",
        ".x-price-primary span",
        "[data-testid='x-price-primary'] span",
        "[data-testid='ux-textual-display'] span",
    ]

    price_text = ""
    for sel in price_candidates:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            price_text = el.get_text(" ", strip=True)
            break

    price = parse_price_eur(price_text)
    if price is None:
        return None

    ship_candidates = [
        "#fshippingCost",
        "#shSummary .logisticsCost",
        "[data-testid='ux-labels-values__shipping']",
        ".ux-labels-values__values-content",
    ]

    ship_text = ""
    for sel in ship_candidates:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            ship_text = el.get_text(" ", strip=True)
            if "versand" in ship_text.lower() or "kostenlos" in ship_text.lower():
                break

    ship = shipping_cost(ship_text)
    return round(price + ship, 2)

# LOAD PRODUCTS FROM EXCEL

def load_products(path="products.xlsx"): #diff. options for the header selection given incase something in future changes
    """
    Reads products.xlsx and returns list of dicts:
    {product, ebay_url}

    Needs headers like:
      Product name, Ebay URL
    """
    df = pd.read_excel(path).fillna("")
    norm = {c.strip().lower(): c for c in df.columns}

    def col(*candidates):
        for cand in candidates:
            key = cand.strip().lower()
            if key in norm:
                return norm[key]
        return None

    product_col = col("product name", "product", "product name", "name")
    ebay_col = col("ebay url", "ebay", "eBay URL", "Ebay URL")

    if not product_col or not ebay_col:
        raise ValueError(
            f"Missing required columns.\n"
            f"Found columns: {list(df.columns)}\n"
            f"Need: Product name, Ebay URL"
        )

    products = []
    for _, row in df.iterrows():
        product = normalize_text(row[product_col])
        ebay_url = normalize_text(row[ebay_col])

        if not product:
            continue

        products.append({
            "product": product,
            "ebay_url": ebay_url
        })

    return products

# DB INSERT

def insert_prices_df_to_mysql(df: pd.DataFrame):
    required = {"Product", "Date", "Seller", "Price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")

    df = df.copy()
    df["Product"] = df["Product"].astype(str).map(normalize_text)
    df["Seller"] = df["Seller"].astype(str).map(normalize_text)
    df["Date"] = df["Date"].astype(str).map(normalize_text)

    df["Price"] = (
        df["Price"]
        .astype(str)
        .str.replace("€", "", regex=False)
        .str.replace("\xa0", " ", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
        .round(2)
    )
# Takes the DataFrame and inserts into MySQL
    # If the row exists (same Product, Date, Seller), it updates the price
    # Otherwise inserts a new row
    df = df.drop_duplicates(subset=["Product", "Date", "Seller"], keep="last")

    sql = f"""
    INSERT INTO {PRICE_TABLE} (Product, Date, Seller, Price) 
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE Price = VALUES(Price);
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    data = list(df[["Product", "Date", "Seller", "Price"]].itertuples(index=False, name=None))
    cur.executemany(sql, data)
    conn.commit()

    print(f"[DB] Inserted/updated {len(data)} rows into {DB_CONFIG['database']}.{PRICE_TABLE}")

    cur.close()
    conn.close()

# EBAY ETL : This is the “main run” function

def run_ebay_etl(products_xlsx="products.xlsx", save_csv=True, write_db=True):
    today = dt.date.today().isoformat()
    products = load_products(products_xlsx)

    rows = []

    for p in products:
        if p["ebay_url"]:
            try:
                price = scrape_ebay_price(p["ebay_url"])
                if price is not None:
                    rows.append({
                        "Product": p["product"],
                        "Date": today,
                        "Seller": SELLER_EBAY,
                        "Price": price
                    })
                    print(f"[OK] Ebay price for {p['product']}: {price}")
                else:
                    print(f"[WARN] No Ebay price for {p['product']}")
            except Exception as e:
                print(f"[WARN] Ebay scrape failed for {p['product']}: {e}")
        else:
            print(f"[WARN] Missing Ebay URL for {p['product']}")

        time.sleep(REQUEST_DELAY_SECONDS)

    df = pd.DataFrame(rows, columns=["Product", "Date", "Seller", "Price"])
    df = df.drop_duplicates(subset=["Product", "Seller", "Date"], keep="last")

    if save_csv:
        os.makedirs("data", exist_ok=True)
        out_csv = f"data/ebay_prices_{today}.csv"
        df.to_csv(out_csv, index=False, encoding="utf-8")
        print(f"[CSV] Saved {len(df)} rows to {out_csv}")

    if write_db and not df.empty:
        insert_prices_df_to_mysql(df)

    return df


if __name__ == "__main__":
    run_ebay_etl(products_xlsx="products.xlsx", save_csv=False, write_db=True) # save csv = False because we don't need csv for now
    # since we are already saving it in database and if needed we can export csv from our database


