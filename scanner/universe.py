import yfinance as yf
import pandas as pd
from config import SECTOR_ETFS


def get_full_universe() -> list[str]:
    """
    Returns S&P 500 tickers via yfinance's built-in method.
    Falls back to a hardcoded core list if that fails.
    """
    try:
        import urllib.request
        import json
        # Use a reliable public API for S&P 500 components
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        df = pd.read_csv(url)
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        print(f"[universe] Loaded {len(tickers)} tickers from GitHub dataset")
        return tickers
    except Exception as e:
        print(f"[universe] GitHub fetch failed: {e}, using fallback list")
        return get_fallback_tickers()


def get_fallback_tickers() -> list[str]:
    """Core 50 blue-chip tickers as a fallback."""
    return [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY",
        "JPM", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "JNJ", "MRK",
        "ABBV", "BAC", "CRM", "NFLX", "KO", "PEP", "TMO", "WMT", "AVGO",
        "MCD", "ACN", "CSCO", "ABT", "DHR", "TXN", "NEE", "PM", "RTX",
        "INTC", "QCOM", "UPS", "HON", "AMGN", "LOW", "INTU", "IBM", "GE",
        "CAT", "BA", "GS", "MS", "BLK"
    ]


def get_sector_returns() -> dict[str, float]:
    """Returns 20-day % return for each sector ETF."""
    returns = {}
    for etf in SECTOR_ETFS:
        try:
            data = yf.download(etf, period="2mo", interval="1d",
                               progress=False, auto_adjust=True)
            if len(data) >= 20:
                close = data["Close"].squeeze()
                r = (close.iloc[-1] / close.iloc[-20] - 1).item()
                returns[etf] = r
        except Exception:
            pass
    return returns


def get_top_sectors(sector_returns: dict, top_n: int = 4) -> list[str]:
    sorted_sectors = sorted(sector_returns, key=sector_returns.get, reverse=True)
    return sorted_sectors[:top_n]


def get_spy_regime() -> str:
    """Returns 'bull', 'bear', or 'neutral'."""
    try:
        data = yf.download("SPY", period="1y", interval="1d",
                           progress=False, auto_adjust=True)
        close = data["Close"].squeeze()
        sma200 = close.rolling(200).mean().iloc[-1].item()
        price = close.iloc[-1].item()
        if price > sma200 * 1.01:
            return "bull"
        elif price < sma200 * 0.99:
            return "bear"
        else:
            return "neutral"
    except Exception as e:
        print(f"[universe] SPY regime check failed: {e}")
        return "neutral"
