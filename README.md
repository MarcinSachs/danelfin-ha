# danelfin-ha

Home Assistant custom integration that pulls **AI scores** from [Danelfin](https://danelfin.com) and exposes them as sensors.

## Sensors created per ticker

| Sensor | Description | Unit |
|---|---|---|
| `sensor.danelfin_TICKER_ai_score` | Overall AI score (1–10) | – |
| `sensor.danelfin_TICKER_fundamental_score` | Fundamental sub-score | – |
| `sensor.danelfin_TICKER_technical_score` | Technical sub-score | – |
| `sensor.danelfin_TICKER_sentiment_score` | Sentiment sub-score | – |
| `sensor.danelfin_TICKER_risk_score` | Risk score | – |
| `sensor.danelfin_TICKER_rating` | Rating: Strong Buy / Buy / Hold / Sell / Strong Sell | – |
| `sensor.danelfin_TICKER_beat_market_probability` | Probability of outperforming S&P 500 in 3 months | % |
| `sensor.danelfin_TICKER_probability_advantage` | Advantage over average stock probability | % |
| `sensor.danelfin_TICKER_price` | Last price | USD |

## Installation

### Via HACS (recommended)
1. Add this repository as a **Custom Repository** in HACS (type: Integration).
2. Install *Danelfin AI Stock Scores*.
3. Restart Home Assistant.

### Manual
1. Copy `custom_components/danelfin/` into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup
1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for *Danelfin*.
3. Enter comma-separated ticker symbols (e.g. `NVDA, AAPL, MSFT`).
4. Set the update interval in hours (default: 4). Danelfin updates scores once per trading day, so 4 h is sufficient.

## How it works

- Fetches `https://danelfin.com/stock/{TICKER}` using `aiohttp`.
- Extracts the embedded Next.js `__NEXT_DATA__` JSON blob (all scores are server-rendered, no headless browser needed).
- Falls back to HTML regex parsing if the JSON structure changes.
- Creates a **fresh HTTP session per update cycle** — this clears cookies on each request, which resolves the session-based access blocks that Danelfin applies.

## Grafana integration

Use one of these approaches to visualize sensors in Grafana:

### Option A – InfluxDB (recommended for historical data)
1. Install the [InfluxDB integration](https://www.home-assistant.io/integrations/influxdb/) in HA.
2. Include the `danelfin_*` entities.
3. Add an InfluxDB datasource in Grafana and query by measurement name.

### Option B – Grafana Infinity plugin (no DB needed)
1. Install the [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) in Grafana.
2. Query the HA REST API: `http://homeassistant.local:8123/api/states/sensor.danelfin_nvda_ai_score`
   with a Bearer token from a Long-Lived Access Token.

## Disclaimer
This integration scrapes publicly available data from Danelfin's website for personal use.
Danelfin AI scores are not investment advice. See [Danelfin's disclaimer](https://danelfin.com/disclaimer).
