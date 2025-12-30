import mysql.connector


# 🔧 CHANGE THESE IF NEEDED
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Megha616@",
    "port": 3306
}

DB_NAME = "price_collection"


def create_database():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    print(f"[OK] Database '{DB_NAME}' created or already exists")

    cursor.close()
    conn.close()


def create_price_table():
    conn = mysql.connector.connect(database=DB_NAME, **DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS PRICE (
            ID BIGINT AUTO_INCREMENT PRIMARY KEY,
            Product VARCHAR(255) NOT NULL,
            Date DATE NOT NULL,
            Seller VARCHAR(255) NOT NULL,
            Price DECIMAL(10,2) NOT NULL,
            UNIQUE KEY uq_product_date_seller (Product, Date, Seller)
        )
    """)

    print("[OK] Table 'PRICE' created or already exists")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_database()
    create_price_table()
