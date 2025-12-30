# Python Price Collection Project

This repository contains a Python-based price collection system developed as part of a university course project.  
The project collects product prices from multiple online platforms, stores them in a MySQL database, and enables historical price analysis.

---

## Project Overview

The project follows an ETL (Extract, Transform, Load) pipeline:

- **Extract** prices from online marketplaces (e.g. Idealo, eBay, Amazon)
- **Transform** the raw data by cleaning prices and including delivery costs
- **Load** daily price snapshots into a MySQL database
- **Analyze** price evolution and seller competitiveness over time

Each execution of the ETL pipeline stores prices together with the execution date, allowing longitudinal analysis.

---

## Repository Structure


- data - Temporary data or CSV outputs
- database - Database schema and helper scripts
- docs - Project documentation (LaTeX / report)
- etl - ETL scripts for different platforms
- requirements.txt - Python dependencies
- README.md - Project documentation


---

## Database Schema

The project uses a MySQL database named `price_collection` with a single table `PRICE`.

**Table: PRICE**
- `ID` – Auto-increment primary key  
- `Product` – Product name  
- `Date` – Date of price collection  
- `Seller` – Seller or platform  
- `Price` – Product price including delivery costs  

A unique constraint on `(Product, Date, Seller)` prevents duplicate entries when the pipeline is executed multiple times on the same day.

---

## Setup Instructions

### 1) Install dependencies

pip install -r requirements.txt

### 2) Create the database
Run the SQL schema located in the database folder using MySQL Workbench or MySQL CLI.

Example:

sql Copy code :-
SOURCE database/schema.sql;

### 3) Configure database connection
Database credentials (host, user, password) must be configured locally inside the ETL scripts or via a local configuration file.

⚠️ Credentials are not stored in this repository for security reasons.

### 4) Run ETL scripts
Each ETL script inserts price data into the shared PRICE table.

Example:

bash
Copy code
python etl/ebay_etl.py
Each run stores a daily snapshot of prices.

Development Notes
The database schema is shared across all components

Historical prices are tracked using the Date column

The project is designed to be easily extended or deployed to cloud environments

Academic Context
This project was developed for a university course focusing on:

Python programming

ETL pipelines

Relational databases

Data validation and reproducibility
