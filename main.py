import json
import os
from datetime import datetime, timezone

from config import (
    POSITIONS_FILE, MAX_POSITIONS, MAX_SECTOR_POSITIONS,
    TIME_STOP_WARNING_DAY, MAX_HOLD_DAYS, PORTFOLIO_VALUE,
    CIRCUIT_BREAKER_DRAWDOWN, MIN_SCORE_LONG
)
from scanner.universe import (
    get_full_universe, get_sector_returns, get_top_sectors, get_spy_regime
)
from scanner.scorer import run_scan
from scanner.alerts import (
    send_buy_signals, send_regime_alert, send_position_alerts, send_alert
)


def load_positions() -> list[dict]:
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE) as f:
        return json.load(f)


def save_positions(positions: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def check_open_positions(positions: list[dict]) -> list[dict]:
    position_alerts = []
    for p in positions:
        days_held = p.get("days_held", 0) + 1
        p["days_held"] = days_held
        if days_held == TIME_STOP_WARNING_DAY:
            position_alerts.append({
                "title": f"TIME STOP WARNING: {p['ticker']}",
                "message": (
                    f"You have held {p['ticker']} for {days_held} days. "
                    f"If no target hit by day {MAX_HOLD_DAYS}, exit at close."
                ),
                "priority": "default"
            })
        if days_held >= MAX_HOLD_DAYS:
            position_alerts.append({
                "title": f"MANDATORY EXIT: {p['ticker']}",
                "message": (
                    f"{p['ticker']} has been held {days_held} days. "
                    f"Exit the full position at today's close. Rule X4."
                ),
                "priority": "high"
            })
    return position_alerts


def filter_by_portfolio_rules(signals: list[dict], positions: list[dict]) -> list[dict]:
    open_count = len(positions)
    slots_available = MAX_POSITIONS - open_count
    if slots_available <= 0:
        return []

    sector_counts: dict[str, int] = {}
    for p in positions:
        etf = p.get("sector_etf", "N/A")
        sector_counts[etf] = sector_counts.get(etf, 0) + 1

    existing_tickers = {p["ticker"] for p in positions}
    filtered = []
    for s in signals:
        if s["ticker"] in existing_tickers:
            continue
        etf = s.get("sector_etf", "N/A")
        if sector_counts.get(etf, 0) >= MAX_SECTOR_POSITIONS:
            continue
        filtered.append(s)
        sector_counts[etf] = sector_counts.get(etf, 0) + 1
        if len(filtered) >= slots_available:
            break
    return filtered


def print_summary(regime: str, top_sectors: list, all_signals: list,
                  actionable: list, positions: list) -> None:
    print()
    print("=" * 60)
    print("  SCAN RESULTS SUMMARY")
    print("=" * 60)

    print(f"\n  Market regime : {regime.upper()}")
    print(f"  Top sectors   : {', '.join(top_sectors) if top_sectors else 'None'}")
    print(f"  Open positions: {len(positions)}/{MAX_POSITIONS}")
    print(f"  Portfolio     : ${PORTFOLIO_VALUE:,.2f}")

    print(f"\n  All stocks scoring >= {MIN_SCORE_LONG} tonight: {len(all_signals)}")
    if all_signals:
        print()
        print(f"  {'#':<3} {'Ticker':<8} {'Score':<7} {'Entry':>7} {'Stop':>7} "
              f"{'Target':>7} {'Shares':>7} {'$Value':>8} {'Signals fired'}")
        print(f"  {'-'*3} {'-'*8} {'-'*7} {'-'*7} {'-'*7} "
              f"{'-'*7} {'-'*7} {'-'*8} {'-'*30}")
        for i, s in enumerate(all_signals, 1):
            fired = [k for k, v in s["signals"].items() if v]
            fired_short = ", ".join(f[:4] for f in fired)
            print(f"  {i:<3} {s['ticker']:<8} {s['score']:<7} "
                  f"${s['entry']:>6.2f} ${s['stop']:>6.2f} "
                  f"${s['target']:>6.2f} {s['shares']:>7} "
                  f"${s['position_value']:>7,.0f}  {fired_short}")

    print()
    print("-" * 60)
    if actionable:
        print(f"  ACTION NEEDED — {len(actionable)} trade(s) to place at open tomorrow:")
        print()
        for s in actionable:
            fired = [k for k, v in s["signals"].items() if v]
            print(f"  >>> BUY {s['ticker']}")
            print(f"      Score         : {s['score']}/10")
            print(f"      Entry price   : ${s['entry']:.2f}  (set limit order at this price)")
            print(f"      Stop loss     : ${s['stop']:.2f}  (set stop order immediately after buying)")
            print(f"      Target (50%)  : ${s['target']:.2f}  (sell half your shares here)")
            print(f"      Shares to buy : {s['shares']}")
            print(f"      Position cost : ${s['position_value']:,.2f}")
            print(f"      Max risk      : ${PORTFOLIO_VALUE * 0.01:.2f} (1% of portfolio)")
            print(f"      ATR           : ${s['atr']:.2f}")
            print(f"      Signals fired : {', '.join(fired)}")
            print()
    else:
        print("  No actionable trades tonight.")
        if len(positions) >= MAX_POSITIONS:
            print("  (Portfolio is full — max positions reached)")
        elif regime == "bear":
            print("  (Bear market regime — preserving cash)")
        else:
            print("  (No stocks met all criteria tonight)")

    print("=" * 60)
    print()


def main():
    print(f"\n{'='*60}")
    print(f"  CSS Trader -- Nightly Scan")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    positions = load_positions()

    position_alerts = check_open_positions(positions)
    if position_alerts:
        send_position_alerts(position_alerts)
        for a in position_alerts:
            print(f"  [POSITION ALERT] {a['title']}: {a['message']}")
    save_positions(positions)

    regime = get_spy_regime()
    print(f"[main] Market regime: {regime}")
    if regime == "bear":
        send_regime_alert("bear")
        print_summary(regime, [], [], [], positions)
        return

    if regime == "neutral":
        send_regime_alert("neutral")

    sector_returns = get_sector_returns()
    top_sectors = get_top_sectors(sector_returns, top_n=4)
    print(f"[main] Top sectors: {top_sectors}")

    tickers = get_full_universe()
    ticker_sector_map: dict[str, str] = {}

    raw_signals = run_scan(tickers, top_sectors, ticker_sector_map)
    actionable = filter_by_portfolio_rules(raw_signals, positions)

    print_summary(regime, top_sectors, raw_signals, actionable, positions)

    send_buy_signals(actionable)
    send_alert(
        "CSS Scan Complete",
        f"Scanned {len(tickers)} stocks. {len(raw_signals)} scored >= 7. "
        f"{len(actionable)} actionable. Open positions: {len(positions)}/{MAX_POSITIONS}.",
        priority="low"
    )


if __name__ == "__main__":
    main()
