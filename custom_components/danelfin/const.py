"""Constants for the Danelfin integration."""

DOMAIN = "danelfin"

# Default scan interval (hours) – Danelfin updates once a day after market close
DEFAULT_SCAN_INTERVAL = 4

# Request timeout (seconds)
REQUEST_TIMEOUT = 30

# Base URL
BASE_URL = "https://danelfin.com/stock/{ticker}"

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
