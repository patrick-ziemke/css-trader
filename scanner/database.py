import json
import os
from datetime import datetime, timezone
from config import POSITIONS_FILE


def load_positions() -> list[dict]:
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_positions(positions: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def load_history() -> list[dict]:
    path = "data/history.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_history(history: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open("data/history.json", "w") as f:
        json.dump(history, f, indent=2)


def load_signals() -> list[dict]:
    path = "data/last_signals.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_signals(signals: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open("data/last_signals.json", "w") as f:
        json.dump(signals, f, indent=2)


def add_position(ticker: str, shares: float, entry_price: float,
                 stop: float, target: float, atr: float,
                 sector_etf: str, score: int) -> None:
    positions = load_positions()
    existing = next((p for p in positions if p["ticker"] == ticker
                     and p["status"] != "CLOSED"), None)
    if existing:
        total_shares = existing["shares_remaining"] + shares
        avg_price = (
            (existing["avg_entry_price"] * existing["shares_remaining"])
            + (entry_price * shares)
        ) / total_shares
        existing["avg_entry_price"] = round(avg_price, 4)
        existing["shares_remaining"] = round(total_shares, 4)
        existing["shares_total"] = round(
            existing.get("shares_total", existing["shares_remaining"]) + shares, 4)
        existing["stop"] = stop
        existing["target"] = target
    else:
        positions.append({
            "ticker": ticker,
            "status": "OPEN",
            "entry_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "avg_entry_price": round(entry_price, 4),
            "shares_total": round(shares, 4),
            "shares_remaining": round(shares, 4),
            "shares_sold": 0.0,
            "stop": round(stop, 4),
            "target": round(target, 4),
            "trailing_stop": round(stop, 4),
            "atr": round(atr, 4),
            "sector_etf": sector_etf,
            "score_at_entry": score,
            "days_held": 0,
            "realized_pnl": 0.0,
            "exit_reason": None,
            "exits": []
        })
    save_positions(positions)


def record_sell(ticker: str, shares_sold: float, exit_price: float,
                exit_reason: str) -> dict:
    positions = load_positions()
    history = load_history()
    pos = next((p for p in positions if p["ticker"] == ticker
                and p["status"] != "CLOSED"), None)
    if not pos:
        return {"error": f"No open position found for {ticker}"}

    shares_sold = round(min(shares_sold, pos["shares_remaining"]), 4)
    pnl = round((exit_price - pos["avg_entry_price"]) * shares_sold, 2)
    pos["realized_pnl"] = round(pos.get("realized_pnl", 0.0) + pnl, 2)
    pos["shares_sold"] = round(pos.get("shares_sold", 0.0) + shares_sold, 4)
    pos["shares_remaining"] = round(pos["shares_remaining"] - shares_sold, 4)
    pos["exits"].append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "shares": shares_sold,
        "price": round(exit_price, 4),
        "pnl": pnl,
        "reason": exit_reason
    })

    if pos["shares_remaining"] <= 0.0001:
        pos["status"] = "CLOSED"
        pos["exit_reason"] = exit_reason
        pos["close_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        history.append(pos)
        positions = [p for p in positions if not (
            p["ticker"] == ticker and p["status"] == "CLOSED"
            and p.get("close_date") == pos["close_date"])]
        save_history(history)
    else:
        pos["status"] = "PARTIAL"

    save_positions(positions)
    return {"success": True, "pnl": pnl, "shares_remaining": pos["shares_remaining"]}


def update_trailing_stops(ticker: str, current_high: float) -> None:
    positions = load_positions()
    for pos in positions:
        if pos["ticker"] == ticker and pos["status"] in ("OPEN", "PARTIAL"):
            new_trail = round(current_high - 1.5 * pos["atr"], 4)
            if new_trail > pos["trailing_stop"]:
                pos["trailing_stop"] = new_trail
    save_positions(positions)


def increment_days_held() -> None:
    positions = load_positions()
    for pos in positions:
        if pos["status"] in ("OPEN", "PARTIAL"):
            pos["days_held"] = pos.get("days_held", 0) + 1
    save_positions(positions)
