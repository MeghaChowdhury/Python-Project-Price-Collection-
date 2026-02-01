dayimport os
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from matplotlib.backends.backend_pdf import PdfPages

# --- SETTINGS LOAD ---
def load_settings():
    settings = {}
    if os.path.exists("settings.txt"):
        with open("settings.txt", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=")
                    settings[key] = value
    return settings

settings = load_settings()

# --- 2. DATABASE LOADING ---
db = mysql.connector.connect(
    host="localhost", 
    user="root",
    password="12345678",
    database="price_collection"
)

query = "SELECT Product, Date, Seller, Price FROM PRICE ORDER BY Product, Date;"
df = pd.read_sql(query, db)
db.close()
df["Date"] = pd.to_datetime(df["Date"])

# -METRICS & RANKING ---
result = (
    df.groupby(["Product","Date"], as_index=False)
      .apply(lambda x: pd.Series({
          "min_price": x["Price"].min(),
          "avg_price": x["Price"].mean(),
          "our_price": x.loc[x["Seller"]=="Our Company","Price"].values[0],
          "our_rank": int(x.sort_values("Price")["Seller"].tolist().index("Our Company") + 1)
      }))
      .reset_index(drop=True)
)

# ---  VISUALIZATION  ---
report_date = df["Date"].max().strftime("%d-%m-%Y")
pdf_filename = f"{report_date}_prices.pdf"

with PdfPages(pdf_filename) as pdf:
    for product in result["Product"].unique():
        temp = result[result["Product"] == product].sort_values("Date").copy()
        temp["Date_str"] = temp["Date"].dt.strftime("%d-%m-%Y")
        
        # Creating the 3 specific plots 
        fig, axes = plt.subplots(3, 1, figsize=(12, 14))
        fig.suptitle(f"Price Analysis: {product}", fontsize=16, fontweight='bold')

        # PLOT 1: Minimal vs Our Price 
        axes[0].plot(temp["Date_str"], temp["min_price"], marker="o", label="Min Price")
        axes[0].plot(temp["Date_str"], temp["our_price"], marker="o", label="Our Price")
        axes[0].set_title("Minimal Price and Our Price")
        axes[0].legend()

        # PLOT 2: Average vs Our Price 
        axes[1].plot(temp["Date_str"], temp["avg_price"], marker="o", label="Average Price")
        axes[1].plot(temp["Date_str"], temp["our_price"], marker="o", label="Our Price")
        axes[1].set_title("Average Price and Our Price")
        axes[1].legend()

        # PLOT 3: The Rank of our price 
        axes[2].plot(temp["Date_str"], temp["our_rank"], marker="o", color='red')
        axes[2].invert_yaxis()
        axes[2].set_title("Our Price Rank Trend")
        
        for ax in axes: ax.tick_params(axis="x", rotation=45)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig()
        plt.close()

# --- EMAIL REPORT  ---
def check_rank_and_email(result_df, pdf_path):
    all_dates = sorted(result_df['Date'].unique(), reverse=True)
    if len(all_dates) < 2: return 

    today, yesterday = all_dates[0], all_dates[1]
    rank_changed = False
    analysis = []

    for product in result_df['Product'].unique():
        prod_data = result_df[result_df['Product'] == product]
        curr = prod_data[prod_data['Date'] == today]
        prev = prod_data[prod_data['Date'] == yesterday]

        if not curr.empty and not prev.empty:
            c_rank, p_rank = int(curr['our_rank'].values[0]), int(prev['our_rank'].values[0])
            if c_rank != p_rank:
                rank_changed = True
            
            analysis.append({
                'product': product, 'prev_rank': p_rank, 
                'curr_rank': c_rank, 'price': float(curr['our_price'].values[0])
            })

    # The email is only sent if the rank has changed
    if rank_changed:
        send_final_email(analysis, today, yesterday, pdf_path)

def send_final_email(analysis, today, yesterday, pdf_path):
    msg = MIMEMultipart()
    msg['Subject'] = f"Rank Change Notification - {today.strftime('%Y-%m-%d')}"
    msg['From'] = settings.get('smtp_user')
    msg['To'] = settings.get('recipients')

    # email body
    body = f"Rank changes detected between {yesterday.date()} and {today.date()}:\n\n"
    body += f"{'Product':<25} {'Prev':<6} {'Curr':<6} {'Status'}\n"
    body += "-" * 55 + "\n"
    
    for item in analysis:
        rank_change = item['curr_rank'] - item['prev_rank']
        status = "📉 Worsened" if rank_change > 0 else "📈 Improved" if rank_change < 0 else "✅ Stable"
        body += f"{item['product'][:24]:<25} {item['prev_rank']:<6} {item['curr_rank']:<6} {status}\n"
    
    body += "\n" + "=" * 55 + "\n"
    body += "See attached PDF for detailed price trend visualizations.\n"
    body += f"\nReport generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    msg.attach(MIMEText(body, 'plain'))
    
    # Attach PDF
    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(pdf_path)}")
        msg.attach(part)

    # Send email
    with smtplib.SMTP(settings['smtp_server'], int(settings['smtp_port'])) as server:
        server.starttls()
        server.login(settings['smtp_user'], settings['smtp_password'])
        server.send_message(msg)
    
    print(f"✓ Email sent successfully to {settings.get('recipients')}")

# Run the check
check_rank_and_email(result, pdf_filename)


