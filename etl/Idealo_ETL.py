import time
from datetime import date
import pandas as pd # pandas reads products.xlsx.
from bs4 import BeautifulSoup #BeautifulSoup parses the HTML Selenium loads.
from selenium import webdriver # selenium opens Idealo pages (because they’re dynamic).
from selenium.webdriver.chrome.options import Options
import mysql.connector

def get_db(): # Every time you call get_db(), it creates a new connection to MySQL.
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_password",  # change here
        database="price_collection"  # change to whatever database name u have
    )


def scrape_idealo(product_name, url):
    """
    Scrape idealo.de using Selenium and insert prices into MySQL as 'Idealo'.
    """
    conn = get_db() # Prepares the DB cursor to run SQL. today is used so rows get stored for the correct day.
    cursor = conn.cursor()
    today = date.today()

    # Selenium headless browser setup : Creates a headless Chrome browser (runs invisibly), loads pages like a real user.
    options = Options()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)

    price_list = []

    try:
        driver.get(url)
        time.sleep(5)  # wait for page to load

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Scrape offer items
        items = soup.select('[data-product-id]')
        print(f"Found {len(items)} items for {product_name}")

        for item in items:
            price_tag = item.select_one('div.text-base.font-medium.text-orange-500')

            if price_tag:
                price_text = (
                    price_tag.text.strip()
                    .replace("€", "")
                    .replace("\xa0", "")
                    .replace(".", "")
                    .replace(",", ".")
                )
                try:
                    price_val = float(price_text)
                except ValueError:
                    continue

                seller_name = "Idealo"  # standard seller name

                # Print price in terminal (so it looks like Amazon/eBay logs)
                print(f"[OK] {product_name} | Idealo price: {price_val} €")

                # Avoid duplicates
                cursor.execute(
                    "SELECT 1 FROM PRICE WHERE Product=%s AND Seller=%s AND Date=%s",
                    (product_name, seller_name, today)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO PRICE (Product, Date, Seller, Price) VALUES (%s,%s,%s,%s)",
                        (product_name, today, seller_name, price_val)
                    )
                    conn.commit()
                    price_list.append((seller_name, price_val))
                    print(f"[DB] Inserted Idealo price for {product_name}")
                else:
                    print(f"[DB] Idealo row already exists for today ({product_name})")

                break  # stop after first valid price (optional, but cleaner for 1 price/day)

        print(f"Scraped {len(price_list)} Idealo offers for {product_name}")

    except Exception as e:
        print(f"Failed fetch for {product_name}: {e}")

    finally:
        driver.quit()
        cursor.close()
        conn.close()

    return price_list


if __name__ == "__main__":
    # Read Excel and normalize column names
    df = pd.read_excel("products.xlsx")
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()

    for _, row in df.iterrows():
        product_name = row["product_name"]
        url = row["idealo_url"]

        print(f"\n Scraping Idealo for: {product_name}")
        scrape_idealo(product_name, url)

        # Our company insertion is intentionally removed/commented out.
        # Our company can be inserted by a separate script or by Amazon ETL.

    print("\n Idealo scraping completed.")

