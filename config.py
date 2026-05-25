import os
from dotenv import load_dotenv

load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC")
PORTFOLIO_VALUE = float(os.getenv("PORTFOLIO_VALUE", "2500"))
RISK_PER_TRADE = 0.01
MAX_POSITIONS = 5
MIN_SCORE_LONG = 7
MIN_VOLUME = 1_000_000
MIN_PRICE = 10.0
ATR_MULTIPLIER_STOP = 2.0
ATR_MULTIPLIER_TARGET = 3.0
ATR_PERIOD = 14
RSI_PERIOD = 14
MAX_HOLD_DAYS = 15
TIME_STOP_WARNING_DAY = 8
CIRCUIT_BREAKER_DRAWDOWN = 0.06
MAX_SECTOR_POSITIONS = 2
POSITIONS_FILE = "data/positions.json"

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"

SECTOR_ETFS = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}