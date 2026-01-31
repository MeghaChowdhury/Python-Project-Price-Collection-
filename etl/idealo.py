import time
from datetime import date
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import mysql.connector

import sys
import io

# Force UTF-8 for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# -----------------------------
# Database connection
# -----------------------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="price"
    )

# -----------------------------
# Setup Chrome driver (headless)
# -----------------------------
def setup_driver():
    options = Options()
    options.add_argument("--headless")  # ✅ headless → no window
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Optional: set user-agent to reduce bot detection
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(40)
    return driver

# -----------------------------
# Scrape Idealo
# -----------------------------
def scrape_idealo(driver, product_name, url):
    conn = get_db()
    cursor = conn.cursor()
    today = date.today()
    price_list = []

    try:
        driver.get(url)
        time.sleep(5)  # wait for JS to load

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        items = soup.select('[data-product-id]')
        print(f"Found {len(items)} items for {product_name}")

        for item in items:
            price_tag = item.select_one('div.text-base.font-medium.text-orange-500')
            if price_tag:
                price_text = price_tag.text.strip().replace("€", "").replace("\xa0", "").replace(".", "").replace(",", ".")
                try:
                    price_val = float(price_text)
                except:
                    continue

                seller_name = "Idealo Partner"

                # Avoid duplicates
                cursor.execute(
                    "SELECT * FROM PRICE WHERE Product=%s AND Seller=%s AND Date=%s",
                    (product_name, seller_name, today)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO PRICE (Product, Date, Seller, Price) VALUES (%s,%s,%s,%s)",
                        (product_name, today, seller_name, price_val)
                    )
                    conn.commit()
                    price_list.append((seller_name, price_val))

        print(f"✅ Scraped {len(price_list)} Idealo offers for {product_name}")

    except Exception as e:
        print(f"❌ Failed fetch for {product_name}: {e}")

    finally:
        cursor.close()
        conn.close()

    return price_list

# -----------------------------
# Main execution
# -----------------------------
if __name__ == "__main__":
    df = pd.read_excel("products.xlsx")
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()

    # ✅ Create Chrome driver once (headless, single instance)
    driver = setup_driver()

    for _, row in df.iterrows():
        product_name = row["product_name"]
        url = row["idealo_url"]
       # our_price = row["our_company_price"]

        print(f"\n🔍 Scraping Idealo for: {product_name}")
        scrape_idealo(driver, product_name, url)

        '''
        # Insert "Our company" price safely
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM PRICE WHERE Product=%s AND Seller=%s AND Date=%s",
                (product_name, "Our company", date.today())
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO PRICE (Product, Date, Seller, Price) VALUES (%s,%s,%s,%s)",
                    (product_name, date.today(), "Our company", our_price)
                )
                conn.commit()
                print(f"✅ Inserted Our company price for {product_name}")
        except Exception as e:
            print(f"❌ DB error inserting our company price: {e}")
        finally:
            cursor.close()
            conn.close()
        '''
    # ✅ Quit driver once at the end
    driver.quit()
    print("\n✅ Idealo scraping completed.")
