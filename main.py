import json
import os
from datetime import datetime, timezone
from dashboard.generate import generate_dashboard

from config import (
    POSITIONS_FILE, MAX_POSITIONS, MAX_SECTOR_POSITIONS,
    PORTFOLIO_VALUE, MIN_SCORE_LONG
)
from scanner.universe import (
    get_full_universe, get_sector_returns, get_top_sectors, get_spy_regime
)
from scanner.scorer import run_scan
from scanner.database import load_positions, save_signals
from scanner.exits import check_exits
from scanner.alerts import (
    send_buy_signals, send_regime_alert, send_position_alerts, send_alert
)


def filter_by_portfolio_rules(signals: list[dict],
                               positions: list[dict]) -> list[dict]:
    open_positions = [p for p in positions if p["status"] in ("OPEN", "PARTIAL")]
    slots_available = MAX_POSITIONS - len(open_positions)
    if slots_available <= 0:
        return []

    sector_counts: dict[str, int] = {}
    for p in open_positions:
        etf = p.get("sector_etf", "N/A")
        sector_counts[etf] = sector_counts.get(etf, 0) + 1

    existing_tickers = {p["ticker"] for p in open_positions}
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
                  actionable: list, positions: list,
                  exit_alerts: list) -> None:
    open_positions = [p for p in positions if p["status"] in ("OPEN", "PARTIAL")]
    print()
    print("=" * 60)
    print("  SCAN RESULTS SUMMARY")
    print("=" * 60)
    print(f"\n  Market regime : {regime.upper()}")
    print(f"  Top sectors   : {', '.join(top_sectors) if top_sectors else 'None'}")
    print(f"  Open positions: {len(open_positions)}/{MAX_POSITIONS}")
    print(f"  Portfolio     : ${PORTFOLIO_VALUE:,.2f}")

    if open_positions:
        print(f"\n  Current holdings:")
        print(f"  {'Ticker':<8} {'Shares':>8} {'Avg Entry':>10} "
              f"{'Stop':>8} {'Target':>8} {'Days':>5} {'Status'}")
        print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*5} {'-'*8}")
        for p in open_positions:
            print(f"  {p['ticker']:<8} {p['shares_remaining']:>8.4f} "
                  f"${p['avg_entry_price']:>9.2f} "
                  f"${p['stop']:>7.2f} ${p['target']:>7.2f} "
                  f"{p['days_held']:>5} {p['status']}")

    if exit_alerts:
        print(f"\n  SELL ALERTS ({len(exit_alerts)}):")
        print("-" * 60)
        for a in exit_alerts:
            print(f"\n  >>> {a['title']}")
            for line in a['message'].split('\n'):
                print(f"      {line}")

    print(f"\n  Stocks scoring >= {MIN_SCORE_LONG} tonight: {len(all_signals)}")
    if all_signals:
        print()
        print(f"  {'#':<3} {'Ticker':<8} {'Score':<7} {'Entry':>7} "
              f"{'Stop':>7} {'Target':>7} {'Shares':>7} {'$Value':>8}")
        print(f"  {'-'*3} {'-'*8} {'-'*7} {'-'*7} {'-'*7} "
              f"{'-'*7} {'-'*7} {'-'*8}")
        for i, s in enumerate(all_signals, 1):
            print(f"  {i:<3} {s['ticker']:<8} {s['score']:<7} "
                  f"${s['entry']:>6.2f} ${s['stop']:>6.2f} "
                  f"${s['target']:>6.2f} {s['shares']:>7} "
                  f"${s['position_value']:>7,.0f}")

    print()
    print("-" * 60)
    if actionable:
        print(f"  BUY SIGNALS — {len(actionable)} trade(s) for tomorrow:")
        for s in actionable:
            fired = [k for k, v in s["signals"].items() if v]
            print(f"\n  >>> BUY {s['ticker']}")
            print(f"      Score         : {s['score']}/10")
            print(f"      Entry price   : ${s['entry']:.2f}")
            print(f"      Stop loss     : ${s['stop']:.2f}")
            print(f"      Target (50%)  : ${s['target']:.2f}")
            print(f"      Suggested     : {s['shares']} shares "
                  f"(${s['position_value']:,.2f})")
            print(f"      Max risk      : ${PORTFOLIO_VALUE * 0.01:.2f}")
            print(f"      Signals fired : {', '.join(fired)}")
    else:
        print("  No new buy signals tonight.")

    print("=" * 60)
    print()


def main():
    print(f"\n{'='*60}")
    print(f"  CSS Trader -- Nightly Scan")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    positions = load_positions()

    # Market regime check
    regime = get_spy_regime()
    print(f"[main] Market regime: {regime}")
    if regime == "bear":
        send_regime_alert("bear")
        print_summary(regime, [], [], [], positions, [])
        return
    if regime == "neutral":
        send_regime_alert("neutral")

    # Sector rankings
    sector_returns = get_sector_returns()
    top_sectors = get_top_sectors(sector_returns, top_n=4)
    print(f"[main] Top sectors: {top_sectors}")

    # Check exit conditions on open positions
    print("[main] Checking exit conditions...")
    exit_alerts = check_exits(top_sectors)
    if exit_alerts:
        send_position_alerts(exit_alerts)
        print(f"[main] {len(exit_alerts)} exit alert(s) sent")

    # Run buy scan
    tickers = get_full_universe()
    ticker_sector_map: dict[str, str] = {}
    raw_signals = run_scan(tickers, top_sectors, ticker_sector_map)

    # Save signals for dashboard to read
    save_signals(raw_signals)

    # Apply portfolio filters
    positions = load_positions()
    actionable = filter_by_portfolio_rules(raw_signals, positions)

    print_summary(regime, top_sectors, raw_signals, actionable,
                  positions, exit_alerts)

    send_buy_signals(actionable)
    send_alert(
        "CSS Scan Complete",
        f"Scanned {len(tickers)} stocks. {len(raw_signals)} scored >= 7. "
        f"{len(actionable)} buy signals. {len(exit_alerts)} sell alerts.",
        priority="low"
    )


if __name__ == "__main__":
    main()
