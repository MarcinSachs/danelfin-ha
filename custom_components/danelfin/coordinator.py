"""Data coordinator for Danelfin integration.

Strategy:
- Fetch https://danelfin.com/stock/{TICKER} once per scan interval.
- Extract the embedded Next.js __NEXT_DATA__ JSON blob — this contains all
  structured data used by the page without the need for a headless browser.
- Fall back to HTML regex parsing if the JSON structure changes.
- Use a fresh aiohttp.ClientSession per-request to avoid session-based
  rate limiting (clearing cookies on each call, which the user discovered
  resolves access blocks).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TICKERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SENSOR_AI_SCORE,
    SENSOR_BEAT_MARKET_PROB,
    SENSOR_FUNDAMENTAL,
    SENSOR_PRICE,
    SENSOR_PRICE_CURRENCY,
    SENSOR_PROB_ADVANTAGE,
    SENSOR_RATING,
    SENSOR_RISK,
    SENSOR_SENTIMENT,
    SENSOR_TECHNICAL,
)

_LOGGER = logging.getLogger(__name__)

# Matches the JSON blob embedded by Next.js in every SSR page
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)

# Lightweight HTML fallbacks – used only when __NEXT_DATA__ parsing fails
_SCORE_RE = re.compile(r'"aiScore"\s*:\s*(\d+)', re.IGNORECASE)
_FUNDAMENTAL_RE = re.compile(r'"fundamentalScore"\s*:\s*(\d+)', re.IGNORECASE)
_TECHNICAL_RE = re.compile(r'"technicalScore"\s*:\s*(\d+)', re.IGNORECASE)
_SENTIMENT_RE = re.compile(r'"sentimentScore"\s*:\s*(\d+)', re.IGNORECASE)


def _derive_rating(ai_score: int | None) -> str:
    """Convert numeric AI score to human-readable rating label."""
    if ai_score is None:
        return "Unknown"
    if ai_score >= 9:
        return "Strong Buy"
    if ai_score >= 7:
        return "Buy"
    if ai_score >= 5:
        return "Hold"
    if ai_score >= 3:
        return "Sell"
    return "Strong Sell"


def _safe_float(value: Any) -> float | None:
    """Return float or None without raising."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Return int or None without raising."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_stock_data(ticker: str, html: str) -> dict[str, Any]:
    """Extract Danelfin stock data from a raw HTML response.

    Tries the embedded __NEXT_DATA__ JSON first; falls back to regex scanning
    of the HTML text so that minor DOM changes don't break everything.
    """
    data: dict[str, Any] = {"ticker": ticker.upper()}

    # ── Primary path: __NEXT_DATA__ JSON ────────────────────────────────────
    match = _NEXT_DATA_RE.search(html)
    if match:
        try:
            next_data = json.loads(match.group(1))
            # The exact path varies with Danelfin's Next.js page structure.
            # Walk the most common patterns we've seen.
            page_props = (
                next_data.get("props", {})
                .get("pageProps", {})
            )

            # Some builds nest data one level deeper under "data" or "stockData"
            stock = (
                page_props.get("stockData")
                or page_props.get("data")
                or page_props
            )

            # AI Scores
            # Danelfin uses camelCase keys in their internal API
            ai_score = _safe_int(
                stock.get("aiScore")
                or stock.get("ai_score")
                or stock.get("score")
            )
            fundamental = _safe_int(
                stock.get("fundamentalScore")
                or stock.get("fundamental_score")
                or stock.get("fundamental")
            )
            technical = _safe_int(
                stock.get("technicalScore")
                or stock.get("technical_score")
                or stock.get("technical")
            )
            sentiment = _safe_int(
                stock.get("sentimentScore")
                or stock.get("sentiment_score")
                or stock.get("sentiment")
            )
            risk = _safe_int(
                stock.get("riskScore")
                or stock.get("risk_score")
                or stock.get("risk")
            )

            # Probability metrics
            beat_prob = _safe_float(
                stock.get("probabilityOfBeatingMarket")
                or stock.get("probability")
                or stock.get("prob")
            )
            prob_advantage = _safe_float(
                stock.get("probabilityAdvantage")
                or stock.get("probAdvantage")
                or stock.get("advantage")
            )

            # Pricing (may be nested under quote/price sub-object)
            quote = stock.get("quote") or stock.get("price") or stock
            price = _safe_float(
                quote.get("close")
                or quote.get("price")
                or quote.get("last")
                if isinstance(quote, dict)
                else None
            )
            currency = (
                (quote.get("currency") or "USD")
                if isinstance(quote, dict)
                else "USD"
            )

            if ai_score is not None:
                data[SENSOR_AI_SCORE] = ai_score
                data[SENSOR_RATING] = _derive_rating(ai_score)
                _LOGGER.debug(
                    "Danelfin %s: AI Score=%s via __NEXT_DATA__", ticker, ai_score
                )

            if fundamental is not None:
                data[SENSOR_FUNDAMENTAL] = fundamental
            if technical is not None:
                data[SENSOR_TECHNICAL] = technical
            if sentiment is not None:
                data[SENSOR_SENTIMENT] = sentiment
            if risk is not None:
                data[SENSOR_RISK] = risk
            if beat_prob is not None:
                data[SENSOR_BEAT_MARKET_PROB] = round(beat_prob, 2)
            if prob_advantage is not None:
                data[SENSOR_PROB_ADVANTAGE] = round(prob_advantage, 2)
            if price is not None:
                data[SENSOR_PRICE] = price
                data[SENSOR_PRICE_CURRENCY] = currency

            # If we got at least the AI score from JSON we're done
            if SENSOR_AI_SCORE in data:
                return data

        except (json.JSONDecodeError, AttributeError, KeyError) as exc:
            _LOGGER.debug(
                "Danelfin %s: __NEXT_DATA__ parse error (%s), falling back to regex",
                ticker,
                exc,
            )

    # ── Fallback path: regex scan of rendered HTML ───────────────────────────
    # The HTML already contains the scores in text form (Next.js SSR), so we
    # can pull them out even without parsing JSON.
    _LOGGER.debug("Danelfin %s: using HTML regex fallback", ticker)

    # AI Score is displayed as "X out of 10" — capture the number
    ai_match = re.search(r"(\d+)\s+out\s+of\s+10", html)
    if ai_match:
        ai_score = int(ai_match.group(1))
        data[SENSOR_AI_SCORE] = ai_score
        data[SENSOR_RATING] = _derive_rating(ai_score)

    # JSON-like values that Next.js bakes into inline <script> props
    for pattern, key in (
        (_FUNDAMENTAL_RE, SENSOR_FUNDAMENTAL),
        (_TECHNICAL_RE, SENSOR_TECHNICAL),
        (_SENTIMENT_RE, SENSOR_SENTIMENT),
    ):
        m = pattern.search(html)
        if m:
            data[key] = int(m.group(1))

    # Probability advantage: "+8.19%" or "-3.5%"
    prob_adv_match = re.search(
        r'probability\s+advantage[^%]*?([+-]?\d+\.?\d*)\s*%', html, re.IGNORECASE
    )
    if prob_adv_match:
        data[SENSOR_PROB_ADVANTAGE] = float(prob_adv_match.group(1))

    # Beat market probability: "61.03%"
    beat_match = re.search(
        r'probability\s+of\s+beating\s+the\s+market[^%]*?(\d+\.?\d*)\s*%',
        html,
        re.IGNORECASE,
    )
    if beat_match:
        data[SENSOR_BEAT_MARKET_PROB] = float(beat_match.group(1))

    # Price: "$183.91"
    price_match = re.search(r'\$([\d,]+\.?\d*)', html)
    if price_match:
        price_str = price_match.group(1).replace(",", "")
        price = _safe_float(price_str)
        if price and price > 0:
            data[SENSOR_PRICE] = price
            data[SENSOR_PRICE_CURRENCY] = "USD"

    return data


class DanelfinCoordinator(DataUpdateCoordinator):
    """Fetch Danelfin AI scores for all tickers in this config entry.

    Tickers are stored in entry.options[CONF_TICKERS] and managed via the
    Options flow (add / remove individually through the UI).
    Returns {TICKER: {sensor_key: value}} after each refresh.
    Uses a fresh aiohttp.ClientSession per cycle for a clean cookie jar.
    """

    def __init__(self, hass: HomeAssistant, tickers: list[str], scan_hours: int) -> None:
        self.tickers: list[str] = [t.strip().upper() for t in tickers]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=scan_hours),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data for all tracked tickers.

        Returns {TICKER: {sensor_key: value}}.
        An empty ticker list (no tickers added yet) returns {} without error.
        Individual ticker failures are logged and skipped so other tickers
        still update successfully.
        """
        if not self.tickers:
            return {}

        results: dict[str, dict[str, Any]] = {}
        connector = aiohttp.TCPConnector(ssl=True)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=REQUEST_HEADERS,
        ) as session:
            for ticker in self.tickers:
                url = BASE_URL.format(ticker=ticker)
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        if resp.status == 429:
                            _LOGGER.warning(
                                "Danelfin rate-limited for %s (HTTP 429). "
                                "Consider increasing the scan interval.",
                                ticker,
                            )
                            continue
                        if resp.status != 200:
                            _LOGGER.warning(
                                "Danelfin returned HTTP %s for %s",
                                resp.status,
                                ticker,
                            )
                            continue

                        html = await resp.text()

                except aiohttp.ClientConnectorError as exc:
                    _LOGGER.error("Connection error for %s: %s", ticker, exc)
                    continue
                except aiohttp.ClientError as exc:
                    _LOGGER.error("Request error for %s: %s", ticker, exc)
                    continue

                data = _parse_stock_data(ticker, html)
                if SENSOR_AI_SCORE not in data:
                    _LOGGER.warning(
                        "Danelfin: no AI Score found for %s – page structure may "
                        "have changed.",
                        ticker,
                    )
                    continue

                results[ticker] = data
                _LOGGER.info(
                    "Danelfin %s: AI Score=%s, Rating=%s",
                    ticker,
                    data.get(SENSOR_AI_SCORE),
                    data.get(SENSOR_RATING),
                )

        return results
