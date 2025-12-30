# import mysql.connector
#
# DB_CONFIG = {
#     "host": "localhost",
#     "user": "root",
#     "password": "Megha616@",
#     "port": 3306,
#     "database": "price_collection"
# }
#
# with mysql.connector.connect(**DB_CONFIG) as conn:
#     with conn.cursor() as cur:
#         cur.execute("SHOW CREATE TABLE PRICE;")
#         table_name, create_stmt = cur.fetchone()
#
# schema_sql = f"CREATE DATABASE IF NOT EXISTS price_collection;\nUSE price_collection;\n\n{create_stmt};\n"
#
# with open("prices_db.sql", "w", encoding="utf-8") as f:
#     f.write(schema_sql)
#
# print("[OK] Exported schema to prices_db.sql")
#
python export_schema.py
