import requests
import pandas as pd
import mysql.connector
import os
from bs4 import BeautifulSoup
from datetime import date



# DATABASE CONNECTION

# Creates and returns a new connection to the MySQL database.
# It uses the database credentials and connects specifically to the 'prices_db' database.
# Every time it is called, a fresh connection is created.
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Megha616@",
        database="price_collection"
    )



# LOAD PRODUCTS FROM EXCEL

# This function reads the Excel file that contains the list of products
# and their corresponding Amazon URLs.
# The file is stored in the 'data' folder.
def load_products():
    return pd.read_excel("products.xlsx")



# AMAZON PRICE SCRAPER

# Takes an Amazon product URL and returns the current price
# as a numeric value (float). If the price cannot be extracted, it returns None.

def scrape_amazon_price(url):

    # HTTP headers are used to simulate a real web browser.
    # This helps avoid being blocked by Amazon's anti-bot system.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # Send an HTTP GET request to the Amazon product page
    response = requests.get(url, headers=headers)

    # Parse the returned HTML into a BeautifulSoup object
    soup = BeautifulSoup(response.text, "html.parser")

    # Try to extract the price using Amazon's main price structure
    price_tag = soup.find("span", {"class": "a-price-whole"})
    frac_tag = soup.find("span", {"class": "a-price-fraction"})

    # If the main price format exists, combine whole and fractional parts
    if price_tag:
        whole = price_tag.text.replace(".", "").replace(",", "").strip()
        frac = frac_tag.text if frac_tag else "00"
        return float(f"{whole}.{frac}")

    # Fallback method: extract the full price from the offscreen element
    price = soup.select_one(".a-price .a-offscreen")
    if price:
        return float(price.text.replace("€","").replace(".","").replace(",","."))

    # If no price could be found, return None
    return None



# INSERT PRICE INTO DATABASE

# Inserts a price record into the PRICE table.
# If a record for the same product, date, and seller already exists,
# the price is updated instead of creating a duplicate entry.

def insert_price(product, seller, price):
    conn = get_db()
    cursor = conn.cursor()

    query = """
    INSERT INTO PRICE (Product, Date, Seller, Price)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE Price = VALUES(Price);
    """

    # Execute the SQL query with the provided values
    cursor.execute(query, (product, date.today(), seller, price))

    # Commit the transaction to save changes in the database
    conn.commit()

    # Close the database connection
    conn.close()



# RUN AMAZON PRICE COLLECTION

# This function runs the full Amazon price collection pipeline:
# 1. Load products from Excel
# 2. Scrape prices from Amazon
# 3. Save the results into the database

def run_amazon_today():
    df = load_products()

    # Loop through each product in the Excel file
    for _, row in df.iterrows():
        product = row["Product name"]
        url = row["Amazon URL"]

        # Scrape the Amazon price for the current product
        price = scrape_amazon_price(url)

        # If a price was successfully retrieved, store it in the database
        if price is not None:
            print(f"{product} | Amazon price: {price} €")
            insert_price(product, "Amazon", price)
        else:
            print(f"{product} | Failed to get price")



# SCRIPT ENTRY POINT

# This ensures that the Amazon price collection runs only
# when this file is executed directly.
if __name__ == "__main__":
    run_amazon_today()
