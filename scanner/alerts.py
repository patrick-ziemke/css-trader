import requests
from config import NTFY_TOPIC


def send_alert(title: str, message: str, priority: str = "default") -> None:
    if not NTFY_TOPIC:
        print(f"[alert] {title}: {message}")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8").decode("latin-1", errors="replace"),
                "Priority": priority,
                "Tags": "chart_increasing",
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[alert] Failed to send notification: {e}")


def send_buy_signals(signals: list[dict]) -> None:
    if not signals:
        send_alert(
            "CSS Scan Complete - No signals tonight",
            "No stocks met the score threshold of 7 tonight. No action needed.",
            priority="low"
        )
        return

    for s in signals[:5]:
        fired = [k for k, v in s["signals"].items() if v]
        fired_str = ", ".join(fired)
        msg = (
            f"Score: {s['score']}/10\n"
            f"Entry: ${s['entry']} | Stop: ${s['stop']} | Target: ${s['target']}\n"
            f"Suggested: {s['shares']} shares (~${s['position_value']:,.0f})\n"
            f"Signals: {fired_str}\n"
            f"Sector ETF: {s['sector_etf']}"
        )
        send_alert(f"BUY SIGNAL: {s['ticker']}", msg, priority="high")


def send_regime_alert(regime: str) -> None:
    if regime == "bear":
        send_alert(
            "BEAR REGIME - No new entries",
            "SPY is below its 200-day SMA. System is in cash-preservation mode. No new positions tonight.",
            priority="high"
        )
    elif regime == "neutral":
        send_alert(
            "NEUTRAL REGIME - Reduced sizing",
            "SPY is near its 200-day SMA. If entering, use 50% of normal position size.",
            priority="default"
        )


def send_position_alerts(alerts: list[dict]) -> None:
    for a in alerts:
        send_alert(a["title"], a["message"], priority=a.get("priority", "default"))
