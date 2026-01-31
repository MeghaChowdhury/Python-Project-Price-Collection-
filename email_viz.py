import os
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from matplotlib.backends.backend_pdf import PdfPages

# SETTINGS

OUR_SELLER = "our company"          # normalized seller name
TOP_N_ALERT = 3                     # highlight if our rank > 3
SEND_DAILY_SUMMARY = True           # True = send email even if no rank change
PRICE_CHANGE_PCT_TRIGGER = 3.0      # optional: include in alert logic (see below). Set None to disable.

# ----------------------------
# SETTINGS LOAD
# ----------------------------
def load_settings():
    settings = {}
    if os.path.exists("settings.txt"):
        with open("settings.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    settings[key.strip()] = value.strip()
    return settings

settings = load_settings()

# ----------------------------
# DATABASE LOADING
# ----------------------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345678",
    database="price_collection"
)

query = "SELECT Product, Date, Seller, Price FROM PRICE ORDER BY Product, Date;"
df = pd.read_sql(query, db)
db.close()

print("Rows pulled:", len(df), flush=True)
if df.empty:
    raise SystemExit("No rows returned from PRICE table. Nothing to plot/email.")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# Normalize seller names
df["Seller_clean"] = df["Seller"].astype(str).str.strip().str.lower()

print("Date min/max:", df["Date"].min(), df["Date"].max(), flush=True)
print("Seller sample:", df["Seller_clean"].unique()[:10], flush=True)

# METRICS & RANKING
def compute_metrics(x: pd.DataFrame) -> pd.Series:
    min_price = x["Price"].min()
    avg_price = x["Price"].mean()

    our_rows = x.loc[x["Seller_clean"] == OUR_SELLER, "Price"]
    our_price = float(our_rows.iloc[0]) if not our_rows.empty else None

    sorted_sellers = x.sort_values("Price")["Seller_clean"].tolist()
    our_rank = (sorted_sellers.index(OUR_SELLER) + 1) if OUR_SELLER in sorted_sellers else None

    return pd.Series({
        "min_price": min_price,
        "avg_price": avg_price,
        "our_price": our_price,
        "our_rank": our_rank
    })

result = (
    df.groupby(["Product", "Date"], as_index=False)
      .apply(compute_metrics, include_groups=False)
      .reset_index(drop=True)
)

print("Result rows:", len(result), flush=True)
if result.empty:
    raise SystemExit("No grouped results produced. Check PRICE table contents.")

# VISUALIZATION (PDF)
report_date = df["Date"].max().strftime("%d-%m-%Y")
pdf_filename = f"{report_date}_prices.pdf"

with PdfPages(pdf_filename) as pdf:
    for product in result["Product"].unique():
        temp = result[result["Product"] == product].sort_values("Date").copy()
        temp["Date_str"] = temp["Date"].dt.strftime("%d-%m-%Y")

        fig, axes = plt.subplots(3, 1, figsize=(12, 14))
        fig.suptitle(f"Price Analysis: {product}", fontsize=16, fontweight="bold")

        axes[0].plot(temp["Date_str"], temp["min_price"], marker="o", label="Min Price")
        axes[0].plot(temp["Date_str"], temp["our_price"], marker="o", label="Our Price")
        axes[0].set_title("Minimal Price and Our Price")
        axes[0].legend()

        axes[1].plot(temp["Date_str"], temp["avg_price"], marker="o", label="Average Price")
        axes[1].plot(temp["Date_str"], temp["our_price"], marker="o", label="Our Price")
        axes[1].set_title("Average Price and Our Price")
        axes[1].legend()

        axes[2].plot(temp["Date_str"], temp["our_rank"], marker="o")
        axes[2].invert_yaxis()
        axes[2].set_title("Our Price Rank Trend")

        for ax in axes:
            ax.tick_params(axis="x", rotation=45)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig()
        plt.close()

print("PDF saved:", pdf_filename, flush=True)

# EMAIL HELPERS
def format_currency(x):
    if pd.isna(x) or x is None:
        return "—"
    return f"{float(x):.2f} €"

def build_summary_table(df_today: pd.DataFrame) -> str:
    """
    Builds an HTML table for today's summary (teacher-friendly).
    """
    table = df_today.copy()

    # Make it readable
    table["min_price"] = table["min_price"].apply(format_currency)
    table["avg_price"] = table["avg_price"].apply(format_currency)
    table["our_price"] = table["our_price"].apply(format_currency)
    table["our_rank"] = table["our_rank"].apply(lambda v: "—" if pd.isna(v) else str(int(v)))

    # Flag top-N
    def rank_flag(v):
        if v == "—":
            return " missing"
        r = int(v)
        return "top" if r <= TOP_N_ALERT else f"not top {TOP_N_ALERT}"

    table["status"] = table["our_rank"].apply(rank_flag)

    # Sort: worst ranks first so warnings stand out
    def sort_key(v):
        if v == "—":
            return 9999
        return int(v)
    table = table.sort_values(by="our_rank", key=lambda s: s.map(sort_key), ascending=False)

    # Select columns
    table = table[["Product", "min_price", "avg_price", "our_price", "our_rank", "status"]]

    return table.to_html(index=False, escape=False)

def send_email(subject: str, html_body: str, pdf_path: str):
    required = ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "recipients"]
    missing = [k for k in required if not settings.get(k)]
    if missing:
        print("Missing email settings keys:", missing, flush=True)
        return

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.get("smtp_user")
    msg["To"] = settings.get("recipients")

    msg.attach(MIMEText(html_body, "html"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(pdf_path)}")
        msg.attach(part)

    print("Sending email to:", msg["To"], flush=True)

    with smtplib.SMTP(settings["smtp_server"], int(settings["smtp_port"])) as server:
        server.starttls()
        server.login(settings["smtp_user"], settings["smtp_password"])
        server.send_message(msg)

    print("Email sent.", flush=True)

# MAIN EMAIL LOGIC
def check_and_email(result_df: pd.DataFrame, pdf_path: str):
    all_dates = sorted(result_df["Date"].unique(), reverse=True)
    if len(all_dates) < 1:
        print("No dates in results. No email.", flush=True)
        return

    today = all_dates[0]
    yesterday = all_dates[1] if len(all_dates) >= 2 else None

    df_today = result_df[result_df["Date"] == today].copy()
    df_yest = result_df[result_df["Date"] == yesterday].copy() if yesterday is not None else pd.DataFrame()

    # Determine "alerts"
    rank_changed_products = []
    price_changed_products = []

    if yesterday is not None and not df_yest.empty:
        merged = df_today.merge(df_yest, on="Product", how="left", suffixes=("_today", "_yest"))

        # rank changes
        for _, row in merged.iterrows():
            rt, ry = row.get("our_rank_today"), row.get("our_rank_yest")
            if pd.notna(rt) and pd.notna(ry) and int(rt) != int(ry):
                rank_changed_products.append((row["Product"], int(ry), int(rt)))

        # price changes (optional)
        if PRICE_CHANGE_PCT_TRIGGER is not None:
            for _, row in merged.iterrows():
                pt, py = row.get("our_price_today"), row.get("our_price_yest")
                if pd.notna(pt) and pd.notna(py) and float(py) != 0:
                    pct = (float(pt) - float(py)) / float(py) * 100.0
                    if abs(pct) >= float(PRICE_CHANGE_PCT_TRIGGER):
                        price_changed_products.append((row["Product"], float(py), float(pt), pct))

    # Create teacher-friendly email body
    summary_table_html = build_summary_table(df_today)

    highlights = []
    # highlight not in top N
    bad = df_today[df_today["our_rank"].notna() & (df_today["our_rank"] > TOP_N_ALERT)]
    if not bad.empty:
        highlights.append(f"<p><b> Not in top {TOP_N_ALERT}:</b> {', '.join(bad['Product'].tolist())}</p>")

    # rank change section
    if rank_changed_products:
        lines = "".join(
            [f"<li>{p}: {old} → {new}</li>" for p, old, new in rank_changed_products]
        )
        highlights.append(f"<p><b>📈 Rank changes since yesterday:</b></p><ul>{lines}</ul>")

    # price change section
    if price_changed_products:
        lines = "".join(
            [f"<li>{p}: {old:.2f} → {new:.2f} ({pct:+.1f}%)</li>"
             for p, old, new, pct in price_changed_products]
        )
        highlights.append(f"<p><b> Significant price changes (≥ {PRICE_CHANGE_PCT_TRIGGER}%):</b></p><ul>{lines}</ul>")

    highlight_html = "".join(highlights) if highlights else "<p>No major alerts today.</p>"

    subject = f"Daily Price Report - {pd.to_datetime(today).strftime('%Y-%m-%d')}"
    html_body = f"""
    <html>
      <body>
        <h2>Daily Price Report ({pd.to_datetime(today).strftime('%Y-%m-%d')})</h2>
        {highlight_html}
        <h3>Summary (min / avg / our price / our rank)</h3>
        {summary_table_html}
        <p>PDF report attached: <b>{os.path.basename(pdf_path)}</b></p>
      </body>
    </html>
    """

    # Decide whether to send
    should_send = SEND_DAILY_SUMMARY or bool(rank_changed_products) or bool(price_changed_products)
    print("Should send email?", should_send, flush=True)

    if should_send:
        send_email(subject, html_body, pdf_path)
    else:
        print("No alerts and daily summary disabled. No email sent.", flush=True)

check_and_email(result, pdf_filename)
