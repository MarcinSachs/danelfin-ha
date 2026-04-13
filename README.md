# danelfin-ha

Home Assistant custom integration that pulls **AI scores** from [Danelfin](https://danelfin.com) via the official Danelfin REST API and exposes them as sensors.

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
| `sensor.danelfin_api_connectivity_status` | Danelfin API connectivity status (global base entry sensor) | – |

Note: `sensor.danelfin_api_connectivity_status` is created only once for the base integration entry and reports the health of the configured API key and connection.

The price sensor is marked as a diagnostic entity and may be hidden by default in some Home Assistant views.

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

This integration uses two kinds of entries:
- A single **base integration entry** for the Danelfin **API key** and shared recommendation options.
- One **ticker entry** per stock or ETF to track.

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for *Danelfin*.
3. On the first screen, enter your Danelfin **API key**, choose which **top-5 recommendation lists** to enable (EU, US, ETF), and optionally adjust the scan interval.
4. After creating the base integration entry, add an additional entry for each ticker you want to track:
   - Enter the **ticker symbol** (e.g. `NVDA`, `SAN.MC`, `BUG`).
   - Select the **market type**: US Stock, European Stock, or ETF.
5. Repeat step 4 for as many tickers as you need.
6. To stop tracking a ticker, delete its ticker entry.
7. To update the API key, recommendation lists, or refresh interval later, choose **Configure** on the Danelfin integration.

### Supported market types

| Type | Example tickers | Danelfin URL |
|---|---|---|
| US Stock | `NVDA`, `AAPL` | `danelfin.com/stock/{ticker}` |
| European Stock | `SAN.MC`, `ADS.DE` | `danelfin.com/stock/eu/{ticker}` |
| ETF | `BUG`, `SPY` | `danelfin.com/etf/{ticker}` |

## How it works

- Uses the official Danelfin REST API for all ticker and recommendation data.
- A central `DataUpdateCoordinator` refreshes data on the configured interval.
- A diagnostic API connectivity sensor helps surface problems with authentication or rate limiting.
- Recommendation lists are also retrieved from the official API, not from HTML scraping.
- Update interval is configurable in hours and defaults to 8 hours.

## Testing without Home Assistant

Run the integration unit tests with pytest:

```bash
pytest tests/test_api.py
pytest tests/test_stage.py
```

## Troubleshooting

- **Invalid API key**: Verify the API key in the integration setup page. The API connectivity sensor will show `Authentication Failed` if the key is rejected.
- **Rate limited**: If the API connectivity sensor reports `Rate Limited`, increase the scan interval in integration options.
- **No sensor data**: Check that each ticker entry is configured with the correct market type and that the base integration entry has a valid API key.

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
This integration uses the official Danelfin API for data access.
Danelfin AI scores are not investment advice. See [Danelfin's disclaimer](https://danelfin.com/disclaimer).

