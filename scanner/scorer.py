from scanner.signals import (
    fetch_data, compute_atr, compute_signals, passes_liquidity_gate
)
from config import (
    PORTFOLIO_VALUE, RISK_PER_TRADE, ATR_MULTIPLIER_STOP,
    ATR_MULTIPLIER_TARGET, MIN_SCORE_LONG
)

SIGNAL_WEIGHTS = {
    "trend_alignment": 2,
    "rsi_bounce": 2,
    "macd_flip": 2,
    "volume_surge": 2,
    "support_confluence": 1,
    "sector_strength": 1,
}


def score_ticker(ticker: str, top_sector_etfs: list[str],
                 ticker_sector_map: dict) -> dict | None:
    df = fetch_data(ticker)
    if df is None:
        return None
    if not passes_liquidity_gate(df):
        return None

    sector_etf = ticker_sector_map.get(ticker)
    signals = compute_signals(df, top_sector_etfs, sector_etf)
    score = sum(SIGNAL_WEIGHTS[k] for k, v in signals.items() if v)

    atr = compute_atr(df)
    entry = df["Close"].iloc[-1].item()
    stop = round(entry - ATR_MULTIPLIER_STOP * atr, 2)
    target = round(entry + ATR_MULTIPLIER_TARGET * atr, 2)
    risk_per_share = entry - stop
    shares = int((PORTFOLIO_VALUE * RISK_PER_TRADE) / risk_per_share) if risk_per_share > 0 else 0
    position_value = round(shares * entry, 2)
    max_position = PORTFOLIO_VALUE * 0.10
    if position_value > max_position:
        shares = int(max_position / entry)
        position_value = round(shares * entry, 2)

    return {
        "ticker": ticker,
        "score": score,
        "signals": signals,
        "entry": round(entry, 2),
        "stop": stop,
        "target": target,
        "atr": round(atr, 2),
        "shares": shares,
        "position_value": position_value,
        "sector_etf": sector_etf or "N/A",
    }


def run_scan(tickers: list[str], top_sector_etfs: list[str],
             ticker_sector_map: dict) -> list[dict]:
    results = []
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        if i % 50 == 0:
            print(f"[scorer] Scanning {i}/{total}...")
        result = score_ticker(ticker, top_sector_etfs, ticker_sector_map)
        if result and result["score"] >= MIN_SCORE_LONG:
            results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"[scorer] {len(results)} stocks scored >= {MIN_SCORE_LONG}")
    return results