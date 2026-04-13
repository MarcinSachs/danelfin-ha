# Migration Plan: From Scraper to Official REST API

This document outlines the roadmap for transitioning the Danelfin Home Assistant integration from a web-scraping approach to the official Danelfin REST API.

## 🎯 Goal
Provide a stable, high-performance, and compliant integration that leverages the official Danelfin API while maintaining the existing user-friendly dashboard experience.

---

## 🏗️ Phase 1: Core API Implementation
- [X] **Create `api.py`**: Implement a clean `DanelfinApiClient` class using `aiohttp`.
    - Support for `x-api-key` header authentication.
    - Robust error handling for HTTP 401/403 (Auth), 429 (Rate Limit), and 5xx errors.
    - Methods to fetch data from `/ranking`, `/sectors`, and `/industries`.
- [X] **Define Data Models**: Create a mapping logic to transform Danelfin JSON responses into structured Python dictionaries for the Coordinator.

## ⚙️ Phase 2: Home Assistant Infrastructure
- [X] **Implement `DataUpdateCoordinator`**:
    - Centralize data fetching to optimize API usage (crucial for Basic Tier users).
    - Implement a smart update interval (default: 480 minutes / 8 hours).
    - Add logic to skip/reduce updates during weekends (Market Closed).
- [X] **Refactor `config_flow.py`**:
    - Add fields for `api_key`.
    - Add optional configuration for `update_interval`.
    - Implement validation to check the API key during setup.

## 📊 Phase 3: Entity Refactoring
- [X] **Main Sensors**:
    - `AI Score`: Main state of the ticker entity.
- [X] **Diagnostic Sensors**:
    - Map `technical`, `fundamental`, `sentiment`, and `low_risk` as individual diagnostic sensors grouped under the Ticker Device.
- [X] **Attributes**:
    - Add `last_updated`, `price`, and `market` as attributes to the main AI Score sensor.
- [X] **Device Grouping**: Ensure all sensors for a specific ticker are correctly linked to a single `Device` via `device_info`.

## 🛠️ Phase 4: Quality of Service & Docs
- [x] **Rate Limit Management**:
    - Add a diagnostic sensor to track API connectivity status.
- [x] **Cleanup**:
    - Remove `beautifulsoup4` and all scraping-related logic.
- [x] **Update Documentation**:
    - Refresh `README.md` with official API setup instructions.
    - Add a "Troubleshooting" section for common API errors.

---

## 📈 API Usage Simulation (Safety Check)
*Calculated for 10 tracked tickers:*
- **Basic Tier (1k calls/mo):** 8-hour interval = ~900 calls/mo (SAFE ✅)
- **Expert Tier (10k calls/mo):** 1-hour interval = ~7,200 calls/mo (SAFE ✅)