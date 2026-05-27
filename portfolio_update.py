import os
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import yfinance as yf


EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
SEND_TO_EMAIL = os.getenv("SEND_TO_EMAIL")

HOLDINGS_FILE = "holdings.json"


def load_holdings():
    with open(HOLDINGS_FILE, "r") as file:
        return json.load(file)


def get_stock_data(ticker):
    stock = yf.Ticker(ticker)

    info = stock.info

    history = stock.history(period="5d")

    if history.empty:
        return None

    current_price = float(history["Close"].iloc[-1])

    if len(history) >= 2:
        previous_close = float(history["Close"].iloc[-2])
    else:
        previous_close = current_price

    daily_change = current_price - previous_close
    daily_change_percent = (daily_change / previous_close) * 100 if previous_close else 0

    company_name = info.get("shortName", ticker)

    news_items = []

    try:
        for item in stock.news[:2]:
            title = item.get("title")
            if title:
                news_items.append(title)
    except Exception:
        pass

    return {
        "ticker": ticker,
        "company_name": company_name,
        "current_price": current_price,
        "previous_close": previous_close,
        "daily_change": daily_change,
        "daily_change_percent": daily_change_percent,
        "news": news_items
    }


def build_email(holdings_data):
    today = datetime.today().strftime("%B %d, %Y")

    total_value = sum(item["position_value"] for item in holdings_data)
    total_daily_change = sum(item["daily_position_change"] for item in holdings_data)

    total_previous_value = total_value - total_daily_change

    if total_previous_value:
        total_daily_percent = (total_daily_change / total_previous_value) * 100
    else:
        total_daily_percent = 0

    sorted_movers = sorted(
        holdings_data,
        key=lambda x: abs(x["daily_change_percent"]),
        reverse=True
    )

    lines = [
        "Good morning Daniel,",
        "",
        f"Here is your portfolio update for {today}.",
        "",
        "Portfolio Snapshot",
        f"Total Portfolio Value: ${total_value:,.2f}",
        f"Daily Change: ${total_daily_change:,.2f} ({total_daily_percent:+.2f}%)",
        "",
        "Top Movers"
    ]

    for item in sorted_movers[:5]:
        lines.append(
            f"• {item['ticker']} ({item['company_name']}): "
            f"{item['daily_change_percent']:+.2f}% "
            f"(${item['daily_position_change']:+.2f} today)"
        )

    lines.extend([
        "",
        "Holdings"
    ])

    for item in holdings_data:
        lines.append(
            f"• {item['ticker']} — {item['shares']} shares — "
            f"${item['current_price']:,.2f}/share — "
            f"Value: ${item['position_value']:,.2f}"
        )

    lines.extend([
        "",
        "News and Notes"
    ])

    any_news = False

    for item in holdings_data:
        if item["news"]:
            any_news = True
            lines.append(f"{item['ticker']}:")
            for news in item["news"]:
                lines.append(f"• {news}")

    if not any_news:
        lines.append("No major headlines found for your holdings this morning.")

    lines.extend([
        "",
        "Overall Take"
    ])

    if total_daily_change > 0:
        lines.append(
            "Your portfolio is up today, led by positive movement in your strongest holdings. "
            "Watch whether the gains are broad-based or concentrated in only a few names."
        )
    elif total_daily_change < 0:
        lines.append(
            "Your portfolio is down today. The biggest thing to watch is whether the weakness is "
            "market-wide or tied to specific holdings."
        )
    else:
        lines.append(
            "Your portfolio is mostly flat today. No major move stands out from the current holdings."
        )

    lines.extend([
        "",
        "This is an automated update based on your manually entered holdings.",
        "",
        "Have a great day."
    ])

    return "\n".join(lines)


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = SEND_TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)


def main():
    holdings = load_holdings()

    holdings_data = []

    for holding in holdings:
        ticker = holding["ticker"].upper()
        shares = float(holding["shares"])

        stock_data = get_stock_data(ticker)

        if stock_data is None:
            holdings_data.append({
                "ticker": ticker,
                "company_name": ticker,
                "shares": shares,
                "current_price": 0,
                "previous_close": 0,
                "daily_change": 0,
                "daily_change_percent": 0,
                "position_value": 0,
                "daily_position_change": 0,
                "news": [f"Could not pull price data for {ticker}. Check ticker symbol."]
            })
            continue

        position_value = shares * stock_data["current_price"]
        daily_position_change = shares * stock_data["daily_change"]

        holdings_data.append({
            **stock_data,
            "shares": shares,
            "position_value": position_value,
            "daily_position_change": daily_position_change
        })

    body = build_email(holdings_data)

    subject = f"Morning Portfolio Update - {datetime.today().strftime('%b %d')}"

    send_email(subject, body)

    print("Portfolio email sent successfully.")


if __name__ == "__main__":
    main()
