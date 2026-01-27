import os
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
from matplotlib.backends.backend_pdf import PdfPages
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime


# Database connection configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "12345678",  # UPDATE THIS WITH YOUR PASSWORD
    "database": "price_collection"
}

# Load email settings from settings.txt
settings = {}
try:
    with open("settings.txt", "r") as f:
        for line in f:
            if "=" in line:
                name, value = line.split("=", 1)
                settings[name.strip()] = value.strip()
    print("Email settings loaded successfully")
except FileNotFoundError:
    print("WARNING: settings.txt not found. Email notification will be skipped.")
    settings = None


#task 3 - generates visualizations + pdf reports

def generate_pdf_report(df):
    """
    Generate PDF report with 3 plots per product:
    - PLOT 1: Minimal price vs Our price over time
    - PLOT 2: Average price vs Our price over time
    - PLOT 3: Rank of our price over time

    Returns: filename of generated PDF
    """

    print("\n[TASK 3] Generating PDF Visualization Report...")

    # Convert Date column to datetime
    df["Date"] = pd.to_datetime(df["Date"])

    # Calculate metrics for each product on each date
    result = (
        df.groupby(["Product", "Date"], as_index=False)
        .apply(lambda x: pd.Series({
            # Lowest price among all sellers
            "min_price": x["Price"].min(),

            # Average market price
            "avg_price": x["Price"].mean(),

            # Price of Our Company
            "our_price": x.loc[x["Seller"] == "Our company", "Price"].values[0]
            if len(x.loc[x["Seller"] == "Our company", "Price"].values) > 0
            else None,

            # Rank of Our Company (1 = cheapest)
            "our_rank": int(
                x.sort_values("Price")["Seller"]
                .tolist()
                .index("Our company") + 1
            ) if "Our company" in x["Seller"].values else None
        }))
        .reset_index(drop=True)
    )

    # Generate filename with current date
    report_date = datetime.now().strftime("%Y-%m-%d")

    # Create reports folder if it doesn't exist
    folder = os.path.join(os.getcwd(), "reports")
    os.makedirs(folder, exist_ok=True)

    # Final PDF file path
    filename = os.path.join(folder, f"{report_date}_prices.pdf")

    print(f"Generating report: {filename}")

    # Create multi-page PDF
    with PdfPages(filename) as pdf:

        # Loop through each product
        for product in result["Product"].unique():

            # Extract data for current product
            temp = (
                result[result["Product"] == product]
                .sort_values("Date")
                .copy()
            )

            # Convert dates to string for plotting
            temp["Date_str"] = temp["Date"].dt.strftime("%Y-%m-%d")

            # Create figure with 3 subplots
            fig, axes = plt.subplots(3, 1, figsize=(12, 14))
            fig.suptitle(product, fontsize=18, fontweight="bold")

            # PLOT 1: MIN PRICE vs OUR PRICE
            ymin1 = 0
            ymax1 = max(
                temp["min_price"].max(),
                temp["our_price"].max()
            ) * 1.1

            axes[0].plot(temp["Date_str"], temp["min_price"],
                         marker="o", lw=2.3, label="Min Price", color="blue")
            axes[0].plot(temp["Date_str"], temp["our_price"],
                         marker="o", lw=2.3, label="Our Price", color="red")
            axes[0].set_ylim(ymin1, ymax1)
            axes[0].set_xlabel("Date")
            axes[0].set_ylabel("Price (€)")
            axes[0].set_title("Minimal Price vs Our Price Over Time")
            axes[0].grid(True, alpha=0.35)
            axes[0].legend()

            # PLOT 2: AVG PRICE vs OUR PRICE
            ymin2 = 0
            ymax2 = max(
                temp["avg_price"].max(),
                temp["our_price"].max()
            ) * 1.1

            axes[1].plot(temp["Date_str"], temp["avg_price"],
                         marker="o", lw=2.3, label="Average Price", color="green")
            axes[1].plot(temp["Date_str"], temp["our_price"],
                         marker="o", lw=2.3, label="Our Price", color="red")
            axes[1].set_ylim(ymin2, ymax2)
            axes[1].set_xlabel("Date")
            axes[1].set_ylabel("Price (€)")
            axes[1].set_title("Average Price vs Our Price Over Time")
            axes[1].grid(True, alpha=0.35)
            axes[1].legend()

            # PLOT 3: RANK TREND
            axes[2].plot(temp["Date_str"], temp["our_rank"],
                         marker="o", lw=2.5, color="purple")
            axes[2].invert_yaxis()  # Rank 1 (best) at top
            axes[2].set_xlabel("Date")
            axes[2].set_ylabel("Rank")
            axes[2].set_title("Rank of Our Price Over Time (Lower is Better)")
            axes[2].grid(alpha=0.35)

            # Rotate x-axis labels
            for ax in axes:
                ax.tick_params(axis="x", rotation=45)

            # Adjust layout and save page
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(bbox_inches="tight", pad_inches=0.4)
            plt.close()

    print(f"✓ PDF report generated successfully: {filename}")
    return filename


# email notification for changes in price

def check_rank_changes(df):
    """
    Check if rank of 'Our company' changed between the two most recent dates.
    Returns list of products with rank changes.
    """

    print("\n[TASK 4] Checking for rank changes...")

    # Convert Date to datetime
    df["Date"] = pd.to_datetime(df["Date"])

    # Calculate rank for each product on each date
    df_ranked = df.copy()
    df_ranked['Rank'] = df_ranked.groupby(['Product', 'Date'])['Price'].rank(method='min')

    # Get the two most recent dates
    all_dates = sorted(df_ranked['Date'].unique(), reverse=True)

    if len(all_dates) < 2:
        print("Not enough data to compare ranks (need at least 2 dates)")
        return []

    today = all_dates[0]
    yesterday = all_dates[1]

    print(f"Comparing ranks between {yesterday.date()} and {today.date()}")

    # Filter for "Our company" only
    ours = df_ranked[df_ranked['Seller'] == 'Our company']

    # Get today's and yesterday's ranks
    rank_today = ours[ours['Date'] == today][['Product', 'Rank']]
    rank_yesterday = ours[ours['Date'] == yesterday][['Product', 'Rank']]

    # Find rank changes
    changes = []
    for _, row in rank_today.iterrows():
        prod = row['Product']
        current_rank = int(row['Rank'])

        prev_row = rank_yesterday[rank_yesterday['Product'] == prod]
        if not prev_row.empty:
            previous_rank = int(prev_row['Rank'].values[0])

            if current_rank != previous_rank:
                changes.append({
                    'product': prod,
                    'previous_rank': previous_rank,
                    'current_rank': current_rank
                })
                print(f"  ✓ Rank change detected: {prod} ({previous_rank} → {current_rank})")

    if not changes:
        print("  No rank changes detected")

    return changes


def send_email(rank_changes, pdf_filename):
    """
    Send email notification about rank changes with PDF report attached.
    Only sends if rank changes occurred and settings are available.
    """

    if not settings:
        print("Skipping email: settings.txt not found")
        return

    if not rank_changes:
        print("No rank changes detected. No email will be sent.")
        return

    print(f"\nSending email notification for {len(rank_changes)} product(s)...")

    # Build email body
    body = "Hello,\n\n"
    body += "The following products have experienced rank changes:\n\n"

    for change in rank_changes:
        if change['current_rank'] < change['previous_rank']:
            direction = "improved ↑"
        else:
            direction = "worsened ↓"

        body += f"• {change['product']}: "
        body += f"Rank {change['previous_rank']} → {change['current_rank']} ({direction})\n"

    body += f"\n\nPlease see the attached PDF report for detailed price analysis.\n"
    body += f"\nReport generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    body += "\nBest regards,\nPrice Tracker System"

    # Create email message
    msg = MIMEMultipart()
    msg['Subject'] = f"Price Alert: Rank Changes Detected ({len(rank_changes)} products)"
    msg['From'] = settings['smtp_user']
    msg['To'] = settings['recipients']

    # Attach body text
    msg.attach(MIMEText(body, 'plain'))

    # Attach PDF report
    try:
        with open(pdf_filename, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            f'attachment; filename={os.path.basename(pdf_filename)}')
            msg.attach(part)
        print("✓ PDF report attached to email")
    except Exception as e:
        print(f"WARNING: Could not attach PDF: {e}")

    # Send email
    try:
        server = smtplib.SMTP(settings['smtp_server'], int(settings['smtp_port']))
        server.starttls()
        server.login(settings['smtp_user'], settings['smtp_password'])
        server.send_message(msg)
        server.quit()
        print(f"✓ Email sent successfully to {settings['recipients']}")
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")


#execution

def main():
    """
    Main workflow:
    1. Connect to database and load price data
    2. Generate PDF visualization 
    3. Check for rank changes 
    4. Send email notification if ranks changed 
    """

    print("=" * 70)
    print("PRICE TRACKER - VISUALIZATION & EMAIL NOTIFICATION SYSTEM")
    print("=" * 70)

    try:
        # Connect to database
        print("\n[1/5] Connecting to database...")
        db = mysql.connector.connect(**db_config)
        print("✓ Database connection established")

        # Load data
        print("\n[2/5] Loading price data from PRICE table...")
        query = """
        SELECT Product, Date, Seller, Price
        FROM PRICE
        ORDER BY Product, Date;
        """
        df = pd.read_sql(query, db)
        db.close()

        if df.empty:
            print("ERROR: No data found in PRICE table!")
            return

        print(f"✓ Loaded {len(df)} price records")
        print(f"✓ Products: {df['Product'].nunique()}")
        print(f"✓ Sellers: {df['Seller'].nunique()}")
        print(f"✓ Date range: {df['Date'].min()} to {df['Date'].max()}")

        # Generate PDF visualization
        print("\n[3/5] Generating PDF visualization report...")
        pdf_filename = generate_pdf_report(df)

        # Check for rank changes
        print("\n[4/5] Analyzing rank changes...")
        rank_changes = check_rank_changes(df)

        # Send email if necessary
        print("\n[5/5] Processing email notification...")
        send_email(rank_changes, pdf_filename)

        print("\n" + "=" * 70)
        print("PROCESS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nGenerated files:")
        print(f"  - PDF Report: {pdf_filename}")
        if rank_changes:
            print(f"  - Email sent: Yes ({len(rank_changes)} product(s) with rank changes)")
        else:
            print(f"  - Email sent: No (no rank changes detected)")

    except mysql.connector.Error as e:
        print(f"\nDATABASE ERROR: {e}")
        print("Please check your database connection settings")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":

    main()

