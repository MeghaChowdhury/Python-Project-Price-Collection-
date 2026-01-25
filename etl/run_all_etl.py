import sys
import subprocess
import datetime as dt
import mysql.connector

# all python codes should be in the same folder + products file
SCRIPTS = [
    "etl/Amazon_ETL.py",
    "etl/Ebay_ETL.py",
    "etl/Idealo_ETL.py",
    "etl/our_company_run_today.py",
]

DB_CONFIG = {
    "host": "localhost",
    "user": "etl_user",
    "password": "Megha616@",
    "port": 3306,
    "database": "price_collection",
}

PRICE_TABLE = "PRICE"


def run_script(path: str) -> int:
    """Run a scraper script exactly as-is."""
    print(f"\n===== RUNNING: {path} =====")
    result = subprocess.run([sys.executable, path], capture_output=False)
    return result.returncode


def db_summary(today_iso: str):
    """Quick proof for demo: show counts per seller for today."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(f"""
        SELECT Seller, COUNT(*) AS cnt
        FROM {DB_CONFIG["database"]}.{PRICE_TABLE}
        WHERE Date = %s
        GROUP BY Seller
        ORDER BY Seller;
    """, (today_iso,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    print("\n===== DB SUMMARY (today) =====")
    for seller, cnt in rows:
        print(f"{seller:15} {cnt}")


if __name__ == "__main__":
    today = dt.date.today().isoformat()

    for script in SCRIPTS:
        code = run_script(script)
        if code != 0:
            print(f"[ERROR] {script} exited with code {code}. Stopping pipeline.")
            sys.exit(code)

    db_summary(today)
    print("\n All ETLs finished.")





