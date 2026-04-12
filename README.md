# danelfin-ha

Home Assistant custom integration that pulls **AI scores** from [Danelfin](https://danelfin.com) and exposes them as sensors.

Supports **US stocks**, **European stocks**, and **ETFs** — both for individual tickers and as automatically-updated **top-5 recommendation lists**.

## Sensors created per ticker

| Sensor | Description | Unit |
|---|---|---|
| `sensor.danelfin_TICKER_ai_score` | Overall AI score (1–10) | – |
| `sensor.danelfin_TICKER_fundamental_score` | Fundamental sub-score | – |
| `sensor.danelfin_TICKER_technical_score` | Technical sub-score | – |
| `sensor.danelfin_TICKER_sentiment_score` | Sentiment sub-score | – |
| `sensor.danelfin_TICKER_risk_score` | Risk score | – |
| `sensor.danelfin_TICKER_rating` | Rating: Strong Buy / Buy / Hold / Sell / Strong Sell | – |
| `sensor.danelfin_TICKER_beat_market_probability` | Probability of outperforming the market / ETF universe in 3 months | % |
| `sensor.danelfin_TICKER_probability_advantage` | Advantage over average stock/ETF probability | % |
| `sensor.danelfin_TICKER_price` | Last price | currency (e.g. USD, EUR) |
| `sensor.danelfin_TICKER_company_name` | Full company / ETF name | – |

## Recommendation sensors (top-5 lists)

When enabled during setup (or via integration options), three additional **devices** are created — one per category — each with 5 position-based sensors:

| Sensor | State | Attributes |
|---|---|---|
| `sensor.danelfin_top_eu_1` … `_5` | Ticker symbol (e.g. `SAN.MC`) | `rank`, `company`, `ai_score`, `rating` |
| `sensor.danelfin_top_us_1` … `_5` | Ticker symbol (e.g. `NVDA`) | `rank`, `company`, `ai_score`, `rating` |
| `sensor.danelfin_top_etf_1` … `_5` | Ticker symbol (e.g. `BUG`) | `rank`, `company`, `ai_score`, `rating` |

Sensors use **position-based names** (neutral) so they remain stable as the ranking changes — the ticker in the state value changes, not the entity ID.

You can enable or disable each recommendation list at any time via **Settings → Devices & Services → Danelfin → Configure**.

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
3. On the first screen, choose which **top-5 recommendation lists** to enable (EU, US, ETF). You can leave all unchecked and enable them later.
4. Click **Add entry** for each individual ticker you want to track:
   - Enter the **ticker symbol** (e.g. `NVDA`, `SAN.MC`, `BUG`).
   - Select the **market type**: US Stock, European Stock, or ETF.
5. Repeat step 4 for as many tickers as you need.
6. To stop tracking a ticker, delete its entry.
7. To change recommendation lists after install, click **Configure** on the Danelfin integration.

### Supported market types

| Type | Example tickers | Danelfin URL |
|---|---|---|
| US Stock | `NVDA`, `AAPL` | `danelfin.com/stock/{ticker}` |
| European Stock | `SAN.MC`, `ADS.DE` | `danelfin.com/stock/eu/{ticker}` |
| ETF | `BUG`, `SPY` | `danelfin.com/etf/{ticker}` |

## How it works

- Fetches the Danelfin page for each ticker using `aiohttp`.
- Danelfin uses Next.js App Router (RSC streaming) — there is no `__NEXT_DATA__` blob. All data is extracted from the server-rendered HTML using CSS class anchors and RSC payload regex parsing.
- Recommendation lists are fetched from Danelfin's ranking pages (`/european-stocks`, `/us-stocks`, `/top-etfs`) and parsed the same way.
- Creates a **fresh HTTP session per update cycle** to avoid session-based access blocks.
- Update interval is fixed at 4 hours (Danelfin publishes scores once per trading day).

## Testing without Home Assistant

A standalone test script is included to validate parsing before deploying to HA:

```bash
python test_danelfin.py NVDA                     # US stock (default)
python test_danelfin.py SAN.MC --market eu       # European stock
python test_danelfin.py BUG --market etf         # ETF
```

A second script validates the recommendation ranking parser:

```bash
python test_rankings2.py                         # fetches and prints top-5 for EU, US, ETF
```

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

