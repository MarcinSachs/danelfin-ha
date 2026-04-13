"""Constants for the Danelfin integration."""

DOMAIN = "danelfin"

# Default scan interval (hours) – Danelfin updates once a day after market close
DEFAULT_SCAN_INTERVAL = 8

# Request timeout (seconds)
REQUEST_TIMEOUT = 30

# Config entry keys
CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MARKET = "market"
MARKET_US = "us"
MARKET_EU = "europe"
MARKET_ETF = "etf"

# Config entry keys
CONF_TICKER = "ticker"     # single ticker symbol stored in entry.data

# ── Recommendations ──────────────────────────────────────────────────────────
# Keys stored in base entry options
CONF_REC_EU = "rec_eu"    # track top 5 European stocks
CONF_REC_US = "rec_us"    # track top 5 US stocks
CONF_REC_ETF = "rec_etf"  # track top 5 ETFs

TOP_N = 5  # number of top positions tracked per category

RANKING_CATEGORIES: dict[str, dict] = {
    CONF_REC_EU: {
        "market": MARKET_EU,
        "asset": None,
        "label": "Top EU Stocks",
        "sensor_prefix": "top_eu",
    },
    CONF_REC_US: {
        "market": MARKET_US,
        "asset": None,
        "label": "Top US Stocks",
 "sensor_prefix": "top_us",
    },
    CONF_REC_ETF: {
        "market": MARKET_US,
        "asset": MARKET_ETF,
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
