
```markdown
# Price Collection Project

This repository contains the implementation of a price collection system developed as part of a university course project.  
The goal of the project is to collect product prices from multiple online platforms, store them in a MySQL database, and analyze price competitiveness over time.

---

## Project Overview

The project follows an ETL (Extract, Transform, Load) approach:

- **Extract** product prices from Idealo, eBay, and Amazon
- **Transform** the data by cleaning prices and including delivery costs
- **Load** daily price snapshots into a MySQL database
- **Analyze** price trends, rankings, and competitiveness over time

Each execution of the ETL pipeline collects the current prices and stores them together with the execution date, enabling historical analysis.

---

## Repository Structure

```

.
├── data/                # Optional: CSV outputs or temporary data
├── database/            # Database schema and SQL files
│   └── prices_db.sql
├── docs/                # Project documentation (LaTeX / PDF)
├── etl/                 # ETL scripts for Idealo, eBay, Amazon
├── requirements.txt     # Python dependencies
└── README.md            # Main project documentation

```

---

## Database Schema

The project uses a MySQL database named `price_collection` with a single table `PRICE`.

**Table: PRICE**
- `ID` – auto-increment primary key  
- `Product` – product name  
- `Date` – date of price collection  
- `Seller` – seller or platform  
- `Price` – price including delivery  

A unique constraint on `(Product, Date, Seller)` prevents duplicate entries when the ETL pipeline is executed multiple times on the same day.

The schema can be created locally using the SQL file:

```

database/prices_db.sql

````

---

## Local Setup Instructions

### 1) Create the database
Open MySQL Workbench or MySQL CLI and run:

```sql
SOURCE database/prices_db.sql;
````

This will create the database `price_collection` and the table `PRICE`.

---

### 2) Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### 3) Configure database credentials

Database credentials (host, user, password) should be configured locally inside the ETL scripts or via a local configuration file.
**Credentials are not stored in this repository for security reasons.**

---

### 4) Run ETL scripts

Each ETL script inserts data into the shared `PRICE` table.

Example:

```bash
python etl/ebay_etl.py
```

Each run stores a daily snapshot of prices.

---

## Development Notes

* The database schema is shared across all team members to ensure consistency.
* Historical price changes are tracked using the `Date` column.
* The project is designed so it can later be deployed to cloud infrastructure (e.g., AWS).

---

## Team Collaboration

All team members use the same database schema locally.
Each component (ETL, visualization, notification) interacts with the shared `PRICE` table.

```

---

## 🔴 IMPORTANT (do this now)
1. Paste this into your **root README**
2. Rename the file to **`README.md`**
3. Commit

Once you do that, your GitHub homepage will look **clean, professional, and complete**.

If you want, send me a **new screenshot after committing**, and I’ll confirm it’s perfect 💙
```
