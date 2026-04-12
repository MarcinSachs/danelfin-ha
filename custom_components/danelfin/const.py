"""Constants for the Danelfin integration."""

DOMAIN = "danelfin"

# Default scan interval (hours) – Danelfin updates once a day after market close
DEFAULT_SCAN_INTERVAL = 4

# Request timeout (seconds)
REQUEST_TIMEOUT = 30

# Base URL (kept for backwards compatibility)
BASE_URL = "https://danelfin.com/stock/{ticker}"

# Market / asset type identifiers
CONF_MARKET = "market"
MARKET_US = "us"
MARKET_EU = "eu"
MARKET_ETF = "etf"

# URL templates per market / asset type
BASE_URL_MAP: dict[str, str] = {
    MARKET_US: "https://danelfin.com/stock/{ticker}",
    MARKET_EU: "https://danelfin.com/stock/eu/{ticker}",
    MARKET_ETF: "https://danelfin.com/etf/{ticker}",
}

# HTTP headers that mimic a regular browser visit
# A realistic User-Agent reduces the chance of being blocked
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Config entry keys
CONF_TICKER = "ticker"     # single ticker symbol stored in entry.data

# ── Recommendations ──────────────────────────────────────────────────────────
# Keys stored in base entry options
CONF_REC_EU = "rec_eu"    # track top 5 European stocks
CONF_REC_US = "rec_us"    # track top 5 US stocks
CONF_REC_ETF = "rec_etf"  # track top 5 ETFs

TOP_N = 5  # number of top positions tracked per category

# Ranking page URLs and link patterns
RANKING_CATEGORIES: dict[str, dict] = {
    CONF_REC_EU: {
        "url": "https://danelfin.com/european-stocks",
        "link_re": r'/stock/eu/([^"/?]+)',
        "market": MARKET_EU,
        "label": "Top EU Stocks",
        "sensor_prefix": "top_eu",
    },
    CONF_REC_US: {
        "url": "https://danelfin.com/us-stocks",
        "link_re": r'"/stock/([A-Z0-9]{1,10})"',
        "market": MARKET_US,
        "label": "Top US Stocks",
        "sensor_prefix": "top_us",
    },
    CONF_REC_ETF: {
        "url": "https://danelfin.com/top-etfs",
        "link_re": r'/etf/([A-Z0-9]{1,10})',
        "market": MARKET_ETF,
        "label": "Top ETFs",
        "sensor_prefix": "top_etf",
    },
}

# AI score rating thresholds (Danelfin convention)
RATING_STRONG_BUY_MIN = 9
RATING_BUY_MIN = 7
RATING_HOLD_MIN = 5
RATING_SELL_MIN = 3
# < 3 → Strong Sell

# Sensor types emitted per ticker
SENSOR_AI_SCORE = "ai_score"
SENSOR_FUNDAMENTAL = "fundamental_score"
SENSOR_TECHNICAL = "technical_score"
SENSOR_SENTIMENT = "sentiment_score"
SENSOR_RISK = "risk_score"
SENSOR_RATING = "rating"
SENSOR_BEAT_MARKET_PROB = "beat_market_probability"
SENSOR_PROB_ADVANTAGE = "probability_advantage"
SENSOR_PRICE = "price"
SENSOR_PRICE_CURRENCY = "price_currency"
SENSOR_COMPANY_NAME = "company_name"
