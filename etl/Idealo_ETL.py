import os
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

import mysql.connector

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


# DB CONFIG (use env vars)
DB_HOST = os.getenv("DB_HOST", "price-collection.c3aqu0qu6kj2.eu-central-1.rds.amazonaws.com")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "")  # your pass
DB_NAME = os.getenv("DB_NAME", "price_collection")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# Seller name for Idealo rows
SELLER_NAME = "Idealo"


def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        connection_timeout=10,
    )


# Selenium setup
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
CHROME_BINARY = os.getenv("CHROME_BINARY", "/usr/bin/google-chrome")


def setup_driver():
    options = Options()
    options.binary_location = CHROME_BINARY

    # EC2-friendly headless flags
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Reduce “automation” signals a bit
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    return driver


def try_accept_cookies(driver, timeout=5):
    """
    Idealo often shows cookie/consent banners. This tries a few common buttons.
    It's okay if nothing is found.
    """
    candidates = [
        (By.XPATH, "//button[contains(., 'Accept')]"),
        (By.XPATH, "//button[contains(., 'I agree')]"),
        (By.XPATH, "//button[contains(., 'Agree')]"),
        (By.XPATH, "//button[contains(., 'Alle akzeptieren')]"),
        (By.XPATH, "//button[contains(., 'Zustimmen')]"),
        (By.XPATH, "//button[contains(., 'Akzeptieren')]"),
        (By.XPATH, "//button[contains(., 'OK')]"),
    ]

    for by, sel in candidates:
        try:
            btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            time.sleep(1)
            return True
        except Exception:
            pass
    return False


def scroll_a_bit(driver, steps=3):
    for _ in range(steps):
        driver.execute_script("window.scrollBy(0, 900);")
        time.sleep(0.8)


# Price extraction helpers
PRICE_REGEX = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+(?:,\d{2})?)\s*€")


def parse_price_to_float(text: str):
    """
    "1.234,56" -> 1234.56
    "799,00" -> 799.0
    """
    t = text.strip().replace("\xa0", " ")
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def extract_price_from_html(soup: BeautifulSoup):
    """
    Try a couple strategies:
    1) Original selector (if still present)
    2) Fallback: find any "€" price in visible text and take the first plausible one
    """
    # Strategy 1 (your old selector)
    tag = soup.select_one("div.text-base.font-medium.text-orange-500")
    if tag and tag.get_text(strip=True):
        val = parse_price_to_float(tag.get_text(strip=True).replace("€", ""))
        if val is not None:
            return val

    # Strategy 2: search for the first € price in text
    text = soup.get_text(" ", strip=True)
    m = PRICE_REGEX.search(text)
    if m:
        val = parse_price_to_float(m.group(1))
        if val is not None:
            return val

    return None


# DB insert

def upsert_price(cursor, conn, product_name, today, seller_name, price_val):
    """
    Requires UNIQUE KEY (Product, Date, Seller) on PRICE table.
    """
    cursor.execute(
        """
        INSERT INTO PRICE (Product, Date, Seller, Price)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE Price = VALUES(Price)
        """,
        (product_name, today, seller_name, price_val),
    )
    conn.commit()


# Scrape Idealo for one product
def scrape_idealo(driver, product_name, url):
    today = date.today()

    conn = get_db()
    cursor = conn.cursor()

    try:
        driver.get(url)

        # wait for page to load some body content
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # cookie banners can block content
        try_accept_cookies(driver, timeout=3)

        # help lazy-load offers
        scroll_a_bit(driver, steps=3)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Try to target offer items if present (not required, but informative)
        items = soup.select("[data-product-id]")
        if items:
            print(f"[INFO] {product_name}: Found {len(items)} offer blocks (data-product-id).")

            # Try within items first (sometimes there are multiple)
            for item in items:
                price_tag = item.select_one("div.text-base.font-medium.text-orange-500")
                if price_tag:
                    price_val = parse_price_to_float(
                        price_tag.get_text(strip=True)
                        .replace("€", "")
                        .replace("\xa0", "")
                    )
                    if price_val is not None:
                        print(f"[OK] {product_name} | Idealo price: {price_val} €")
                        upsert_price(cursor, conn, product_name, today, SELLER_NAME, price_val)
                        print(f"[DB] Upserted Idealo price for {product_name}")
                        return price_val

        # Fallback: extract from whole page
        price_val = extract_price_from_html(soup)
        if price_val is not None:
            print(f"[OK] {product_name} | Idealo price: {price_val} € (fallback)")
            upsert_price(cursor, conn, product_name, today, SELLER_NAME, price_val)
            print(f"[DB] Upserted Idealo price for {product_name}")
            return price_val

        print(f"[WARN] {product_name} | No Idealo price found.")
        return None

    except Exception as e:
        print(f"[ERROR] Idealo failed for {product_name}: {e}")
        return None

    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


# Main
def load_products_excel():
    """
    Works whether you run from etl/ or from project root.
    """
    candidates = ["products.xlsx", os.path.join("etl", "products.xlsx")]
    for path in candidates:
        if os.path.exists(path):
            df = pd.read_excel(path)
            df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()
            return df
    raise FileNotFoundError("products.xlsx not found (looked in ./products.xlsx and ./etl/products.xlsx)")


if __name__ == "__main__":
    if not DB_PASS:
        print("[FATAL] DB_PASS is empty. Set it first, e.g.:")
        print("  export DB_PASS='your_rds_password'")
        raise SystemExit(1)

    df = load_products_excel()

    driver = setup_driver()
    try:
        for _, row in df.iterrows():
            product_name = row.get("product_name")
            url = row.get("idealo_url")

            if not product_name or not url or str(url).strip().lower() in ("nan", ""):
                continue

            print(f"\n Scraping Idealo for: {product_name}")
            scrape_idealo(driver, product_name, str(url))

    finally:
        driver.quit()

    print("\n Idealo scraping completed.")
