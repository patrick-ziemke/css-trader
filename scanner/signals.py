import numpy as np
import pandas as pd
import yfinance as yf
from config import ATR_PERIOD, RSI_PERIOD, MIN_VOLUME, MIN_PRICE


def fetch_data(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 60:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        return df
    except Exception:
        return None


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def compute_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    delta = df["Close"].squeeze().diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs))


def compute_macd(df: pd.DataFrame) -> pd.Series:
    close = df["Close"].squeeze()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - signal_line


def passes_liquidity_gate(df: pd.DataFrame) -> bool:
    avg_vol = float(df["Volume"].squeeze().iloc[-20:].mean())
    last_price = float(df["Close"].squeeze().iloc[-1])
    return avg_vol >= MIN_VOLUME and last_price >= MIN_PRICE


def compute_signals(df: pd.DataFrame, top_sector_etfs: list[str],
                    ticker_sector_etf: str | None) -> dict:
    close = df["Close"].squeeze()
    signals = {}

    # Signal 1: Trend alignment (+2)
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    price = float(close.iloc[-1])
    signals["trend_alignment"] = (price > sma50) and (sma50 > sma200)

    # Signal 2: RSI oversold bounce (+2)
    rsi = compute_rsi(df)
    rsi_last3 = rsi.iloc[-4:-1]
    rsi_today = float(rsi.iloc[-1])
    rsi_yesterday = float(rsi.iloc[-2])
    signals["rsi_bounce"] = (
        bool((rsi_last3 < 35).any()) and
        rsi_today > rsi_yesterday
    )

    # Signal 3: MACD histogram flip (+2)
    hist = compute_macd(df)
    signals["macd_flip"] = (
        float(hist.iloc[-2]) < 0 and float(hist.iloc[-1]) > 0
    )

    # Signal 4: Volume surge (+2)
    avg_vol_20 = float(df["Volume"].squeeze().iloc[-21:-1].mean())
    today_vol = float(df["Volume"].squeeze().iloc[-1])
    signals["volume_surge"] = today_vol > 1.5 * avg_vol_20

    # Signal 5: Support confluence (+1)
    sma20 = float(close.rolling(20).mean().iloc[-1])
    low_20 = float(close.iloc[-20:].min())
    signals["support_confluence"] = (
        abs(price - sma20) / sma20 < 0.02 or
        abs(price - low_20) / low_20 < 0.02
    )

    # Signal 6: Sector strength (+1)
    if ticker_sector_etf and top_sector_etfs:
        signals["sector_strength"] = ticker_sector_etf in top_sector_etfs
    else:
        signals["sector_strength"] = False

    return signals
