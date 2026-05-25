import yfinance as yf
from scanner.database import (
    load_positions, update_trailing_stops, increment_days_held
)
from scanner.scorer import score_ticker
from config import TIME_STOP_WARNING_DAY, MAX_HOLD_DAYS


def fetch_todays_data(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 1:
            return None
        row = df.iloc[-1]
        return {
            "high": float(row["High"].iloc[0] if hasattr(row["High"], 'iloc') else row["High"]),
            "low": float(row["Low"].iloc[0] if hasattr(row["Low"], 'iloc') else row["Low"]),
            "close": float(row["Close"].iloc[0] if hasattr(row["Close"], 'iloc') else row["Close"]),
        }
    except Exception as e:
        print(f"[exits] Failed to fetch data for {ticker}: {e}")
        return None


def check_exits(top_sector_etfs: list[str]) -> list[dict]:
    positions = load_positions()
    alerts = []

    increment_days_held()

    for pos in positions:
        if pos["status"] not in ("OPEN", "PARTIAL"):
            continue

        ticker = pos["ticker"]
        data = fetch_todays_data(ticker)
        if not data:
            continue

        day_low = data["low"]
        day_high = data["high"]
        close = data["close"]
        days_held = pos.get("days_held", 0)
        stop = pos["stop"]
        target = pos["target"]
        trailing_stop = pos.get("trailing_stop", stop)
        unrealized_pnl = round(
            (close - pos["avg_entry_price"]) * pos["shares_remaining"], 2)
        pnl_pct = round(
            (close - pos["avg_entry_price"]) / pos["avg_entry_price"] * 100, 2)

        # Update trailing stop based on today's high
        update_trailing_stops(ticker, day_high)

        # Rule 1: Stop loss hit (day low touched or broke stop)
        if day_low <= stop:
            alerts.append({
                "ticker": ticker,
                "rule": "STOP_HIT",
                "title": f"STOP HIT: {ticker}",
                "message": (
                    f"Today's low ${day_low:.2f} touched your stop ${stop:.2f}.\n"
                    f"Shares remaining: {pos['shares_remaining']}\n"
                    f"Suggested exit: market sell all remaining shares.\n"
                    f"Log your actual sell price in the dashboard."
                ),
                "priority": "high"
            })
            continue

        # Rule 2: Trailing stop hit (close below trailing stop)
        if close <= trailing_stop and pos["status"] == "PARTIAL":
            alerts.append({
                "ticker": ticker,
                "rule": "TRAILING_STOP",
                "title": f"TRAILING STOP: {ticker}",
                "message": (
                    f"Close ${close:.2f} is below trailing stop ${trailing_stop:.2f}.\n"
                    f"Shares remaining: {pos['shares_remaining']}\n"
                    f"Unrealized P&L: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                    f"Consider selling remaining shares. Log in dashboard."
                ),
                "priority": "high"
            })
            continue

        # Rule 3: Target hit (day high touched target)
        if day_high >= target and pos["status"] == "OPEN":
            half_shares = round(pos["shares_remaining"] / 2, 4)
            alerts.append({
                "ticker": ticker,
                "rule": "TARGET_HIT",
                "title": f"TARGET HIT: {ticker}",
                "message": (
                    f"Today's high ${day_high:.2f} reached your target ${target:.2f}.\n"
                    f"Sell half: {half_shares} shares at or near ${target:.2f}.\n"
                    f"Let remaining {half_shares} shares run with trailing stop.\n"
                    f"Log your actual sell price in the dashboard."
                ),
                "priority": "high"
            })
            continue

        # Rule 4: Signal reversal — rescan the stock
        try:
            rescan = score_ticker(ticker, top_sector_etfs, {})
            if rescan and rescan["score"] < 3:
                alerts.append({
                    "ticker": ticker,
                    "rule": "SIGNAL_REVERSAL",
                    "title": f"SIGNAL REVERSAL: {ticker}",
                    "message": (
                        f"Setup score dropped to {rescan['score']}/10 (was {pos['score_at_entry']}).\n"
                        f"Current P&L: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                        f"Shares: {pos['shares_remaining']} @ avg ${pos['avg_entry_price']:.2f}\n"
                        f"Consider exiting. Log in dashboard if you sell."
                    ),
                    "priority": "default"
                })
                continue
        except Exception:
            pass

        # Rule 5: Time stop warning — day 8
        if days_held == TIME_STOP_WARNING_DAY:
            alerts.append({
                "ticker": ticker,
                "rule": "TIME_WARNING",
                "title": f"TIME WARNING: {ticker}",
                "message": (
                    f"Held {days_held} days. Mandatory exit at day {MAX_HOLD_DAYS}.\n"
                    f"Current P&L: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                    f"Close: ${close:.2f} | Stop: ${stop:.2f} | Target: ${target:.2f}"
                ),
                "priority": "default"
            })

        # Rule 6: Mandatory time stop — day 15
        if days_held >= MAX_HOLD_DAYS:
            alerts.append({
                "ticker": ticker,
                "rule": "TIME_EXIT",
                "title": f"MANDATORY EXIT: {ticker}",
                "message": (
                    f"Held {days_held} days — maximum reached. Exit today at close.\n"
                    f"Shares remaining: {pos['shares_remaining']}\n"
                    f"Current P&L: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                    f"Log your exit price in the dashboard."
                ),
                "priority": "high"
            })

    return alerts
