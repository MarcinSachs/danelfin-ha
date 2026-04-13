<div align="center">

# 📈 Danelfin for Home Assistant
**Artificial Intelligence for your Investment Portfolio**

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/MarcinSachs/danelfin-ha?style=flat-square)](https://github.com/MarcinSachs/danelfin-ha)
![GitHub stars](https://img.shields.io/github/stars/MarcinSachs/danelfin-ha?style=flat-square)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarcinSachs&repository=danelfin-ha&category=Integration)

[Official Website](https://danelfin.com) | [API Documentation](https://danelfin.com/api-rest) | [Support the Project](https://github.com/MarcinSachs/danelfin-ha/issues)

---

<img src="https://cdn.danelfin.com/assets/next/images/danelfinLogos/logoDanelfin.svg" width="300" alt="Danelfin Logo">

</div>

## ✨ Key Features
Monitor your stocks and ETFs using Danelfin's **AI-driven scores**. This integration brings professional-grade financial analytics directly to your Home Assistant dashboard.

* 🚀 **AI Smart Scores:** Track the overall AI Score (1-10) and sub-scores (Fundamental, Technical, Sentiment).
* 🇪🇺 **Global Coverage:** Support for US Stocks, European Stocks (RIC format), and ETFs.
* 🏆 **Top-5 Recommendations:** Automatically updated lists for the best investment opportunities in each market.
* 📊 **Professional Analytics:** Monitor "Beat Market Probability" and price data for every tracked ticker.
* ⚡ **Efficiency:** Built on the official REST API with `DataUpdateCoordinator` to save your API quota.

---

## 🛠 Installation

### Option 1: HACS (Recommended)
The easiest way to install and stay updated.

[![Open your Home Assistant instance and open a repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarcinSachs&repository=danelfin-ha&category=Integration)

1. Click the button above or go to **HACS** → **Integrations**.
2. Select **Custom repositories** and add `https://github.com/MarcinSachs/danelfin-ha` as an **Integration**.
3. Search for **Danelfin AI Stock Scores** and install it.
4. **Restart** Home Assistant.

### Option 2: Manual
1. Download the `danelfin` folder from `custom_components/`.
2. Paste it into your `config/custom_components/` directory.
3. **Restart** Home Assistant.

---

## ⚙️ Configuration

1. **Base Entry:** Go to **Settings** → **Devices & Services** → **Add Integration** and search for **Danelfin**.
   - Enter your **API Key**.
   - Enable the **Top-5 Lists** you want to track.
   - Set the **Update Interval** (default: 8h).
2. **Adding Tickers:** Add more entries of the Danelfin integration to track specific stocks/ETFs.
   - Enter the ticker (e.g., `NVDA`, `AAPL`, `SAP.DE`).
   - Select the correct **Market Type**.

---

## 📋 Available Sensors

### Individual Ticker Sensors
| Category | Sensors |
| :--- | :--- |
| **Main AI** | AI Score, Rating (Buy/Sell), Beat Market Probability |
| **Sub-Scores** | Fundamental, Technical, Sentiment, Risk |
| **Market Data** | Last Price, Probability Advantage, Company Name |
| **System** | API Connectivity Status |

### Recommendation Lists (Top-5)
Stay on top of the market with position-based sensors that update as the ranking changes:
* `sensor.danelfin_top_us_1..5` (US Market)
* `sensor.danelfin_top_eu_1..5` (European Market)
* `sensor.danelfin_top_etf_1..5` (ETFs)

---

## 📈 Visualizing Data
### Grafana & InfluxDB
For historical tracking of AI scores, we recommend using InfluxDB. You can easily create charts showing how a stock's AI rating has evolved over time.

---

## ☕ Support the Project
If you find my work useful, please consider supporting me!

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=marcinsachs&button_colour=28a745&font_colour=ffffff&font_family=Inter&outline_colour=000000&coffee_colour=FFDD00)](https://www.buymeacoffee.com/marcinsachs)

---

## ⚠️ Disclaimer
**This integration is for informational purposes only.** Danelfin AI scores are not investment advice. Please refer to [Danelfin's full disclaimer](https://danelfin.com/disclaimer).

---

<div align="center">
Developed with ❤️ by <a href="https://github.com/MarcinSachs">Marcin Sachs</a>
</div>