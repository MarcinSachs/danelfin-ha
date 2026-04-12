"""Data coordinator for Danelfin integration.

Strategy:
- Fetch https://danelfin.com/stock/{TICKER} once per scan interval.
- Parse the server-rendered HTML using CSS class anchors.
  Danelfin uses Next.js App Router (RSC streaming) — there is no
  __NEXT_DATA__ blob.  Score data is in the rendered HTML body;
  price data is in the RSC payload (escaped JSON in <script> tags).
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL_MAP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MARKET_ETF,
    MARKET_US,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SENSOR_AI_SCORE,
    SENSOR_BEAT_MARKET_PROB,
    SENSOR_COMPANY_NAME,
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

# backslash + double-quote — appears in RSC payload (escaped JS strings)
_BSLASH_QUOTE = chr(92) + chr(34)

_SUBSCORE_LABEL_MAP: dict[str, str] = {
    "fundamental": SENSOR_FUNDAMENTAL,
    "technical": SENSOR_TECHNICAL,
    "sentiment": SENSOR_SENTIMENT,
    "low risk": SENSOR_RISK,
}


def _derive_rating(ai_score: int | None) -> str:
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
    try:
        return float(str(value).replace(",", "").replace("+", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_stock_data(ticker: str, html: str, is_etf: bool = False) -> dict[str, Any]:
    """Extract Danelfin stock data from a raw HTML response.

    Danelfin uses Next.js App Router (RSC streaming) — data is embedded in
    the server-rendered HTML body using CSS class anchors.  Price props are
    in the RSC payload (escaped JSON strings inside <script> tags).
    """
    ticker = ticker.upper()
    data: dict[str, Any] = {"ticker": ticker}

    # ── Company name ─────────────────────────────────────────────────────────
    m = re.search(r'class="[^"]*TickerName_company[^"]*"[^>]*>([^<]+)<', html)
    if m:
        data[SENSOR_COMPANY_NAME] = m.group(1).strip()

    # ── AI Score (main gauge) ─────────────────────────────────────────────────
    # AiScoreCard_wrapper contains: aria-label="N out of 10" (rendered HTML)
    # or \"aria-label\":\"N out of 10\" (RSC payload).  Both handled by [=:\\"]+?
    ai_card = re.search(r'AiScoreCard_wrapper', html)
    if ai_card:
        snippet = html[ai_card.start(): ai_card.start() + 5000]
        m = re.search(r'aria-label[=:\\"]+?(\d+) out of 10', snippet)
        if m:
            ai_score = _safe_int(m.group(1))
            if ai_score is not None:
                data[SENSOR_AI_SCORE] = ai_score
                data[SENSOR_RATING] = _derive_rating(ai_score)

    # If rendered HTML has the rating text directly, prefer that over derived.
    m = re.search(
        r'class="[^"]*AiScoreCard_actionText[^"]*"[^>]*>([^<]+)<', html)
    if m:
        data[SENSOR_RATING] = m.group(1).strip()

    # ── Sub-scores (Fundamental / Technical / Sentiment / Low Risk) ───────────
    # AiScoreBreakdown_scoreList appears multiple times: first as a loading
    # skeleton, later in RSC payload (escaped JSON) and rendered HTML.
    # Normalize escaped quotes in every chunk so the aria-label regex works
    # regardless of which occurrence we land on.
    for bd_m in re.finditer(r'AiScoreBreakdown_scoreList', html):
        ul_end = html.find('</ul>', bd_m.start())
        raw_chunk = html[bd_m.start(
        ): ul_end] if ul_end > 0 else html[bd_m.start(): bd_m.start() + 15000]
        chunk = raw_chunk.replace(_BSLASH_QUOTE, chr(34))
        if 'aria-label' not in chunk:
            continue
        for sm in re.finditer(
            r'aria-label="(\d+) out of 10".*?<span>([^<]+)</span>',
            chunk,
            re.DOTALL,
        ):
            label = sm.group(2).strip().lower()
            key = _SUBSCORE_LABEL_MAP.get(label)
            if key:
                data[key] = _safe_int(sm.group(1))
        if any(k in data for k in _SUBSCORE_LABEL_MAP.values()):
            break  # found real data, stop

    # ── Price (RSC payload) ───────────────────────────────────────────────────
    # TickerPrice_price appears multiple times (CSS rules, RSC payload, etc.).
    # Iterate all occurrences and use the first window that has a "value" field.
    for pm in re.finditer(r'TickerPrice_price', html):
        window = html[pm.start(): pm.start() +
                      400].replace(_BSLASH_QUOTE, chr(34))
        vm = re.search(r'"value"\s*:\s*([\d.]+)', window)
        if vm:
            data[SENSOR_PRICE] = _safe_float(vm.group(1))
            cm = re.search(r'"currency"\s*:\s*"([A-Z]+)', window)
            data[SENSOR_PRICE_CURRENCY] = cm.group(1) if cm else "USD"
            break

    # ── Probability advantage ─────────────────────────────────────────────────
    m = re.search(
        r'AIScoreAlphaFactors_probabilityAdvantage[^"]*"'
        r'.*?PercentageDisplay_percentageDisplay[^"]*"[^>]*>'
        r'([+-]?\d+\.?\d*)\s*%',
        html,
        re.DOTALL,
    )
    if m:
        data[SENSOR_PROB_ADVANTAGE] = _safe_float(m.group(1))
    else:
        # Fallback: text pattern (ETFs use a different component/layout)
        adv_target = r'the ETF universe' if is_etf else r'the market'
        fb = re.search(
            rf'{re.escape(ticker)}\s+probability advantage of beating\s+{adv_target}'
            r'.*?\(3M\).*?([+-]\d+\.?\d*)\s*%',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if fb:
            data[SENSOR_PROB_ADVANTAGE] = _safe_float(fb.group(1))
    # ── Probability of beating the market / ETF universe (3M) ───────────────
    # Stocks: "{TICKER} probability of beating the market (3M)"
    # ETFs:   "{TICKER} probability of beating the ETF universe (3M)"
    beat_target = r'the ETF universe' if is_etf else r'the market'
    m = re.search(
        rf'{re.escape(ticker)}\s+probability of beating\s+{beat_target}[^(]*\(3M\)'
        r'</span>.*?<span[^>]*PercentageDisplay[^>]*>([\d.]+)\s*%',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        data[SENSOR_BEAT_MARKET_PROB] = _safe_float(m.group(1))

    return data


class DanelfinCoordinator(DataUpdateCoordinator):
    """Fetch Danelfin AI scores for all tickers in this config entry.

    One entry per ticker. Returns {TICKER: {sensor_key: value}} after each refresh.
    Uses a fresh aiohttp.ClientSession per cycle for a clean cookie jar.
    """

    def __init__(self, hass: HomeAssistant, tickers: list[str], scan_hours: int, market: str = MARKET_US) -> None:
        self.tickers: list[str] = [t.strip().upper() for t in tickers]
        self.market: str = market

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
                url = BASE_URL_MAP.get(
                    self.market, BASE_URL_MAP[MARKET_US]).format(ticker=ticker)
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

                data = _parse_stock_data(
                    ticker, html, is_etf=(self.market == MARKET_ETF))
                if SENSOR_AI_SCORE not in data:
                    _LOGGER.warning(
                        "Danelfin: no AI Score found for %s – page structure may "
                        "have changed. Entities will show as unavailable until data "
                        "is received.",
                        ticker,
                    )
                # Always add to results so entities stay available;
                # individual sensor values will be None when data is missing.
                results[ticker] = data
                _LOGGER.info(
                    "Danelfin %s: AI Score=%s, Rating=%s",
                    ticker,
                    data.get(SENSOR_AI_SCORE),
                    data.get(SENSOR_RATING),
                )

        if not results and self.tickers:
            raise UpdateFailed(
                "Danelfin: failed to retrieve data for any ticker. "
                "Check network connectivity or whether the site is blocking requests."
            )

        return results
