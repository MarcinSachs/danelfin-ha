"""Coordinator and parser for Danelfin top-ranking recommendation pages.

Fetches the top-N entries from:
  - https://danelfin.com/european-stocks  (top EU stocks)
  - https://danelfin.com/us-stocks        (top US stocks)
  - https://danelfin.com/top-etfs         (top ETFs)

Data structure returned per category:
    {
        1: {"ticker": "SAN.MC", "company": "Banco Santander SA", "ai_score": 10,
            "rating": "Strong Buy", "rank": 1},
        2: {...},
        ...
    }
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
    CONF_REC_ETF,
    CONF_REC_EU,
    CONF_REC_US,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RANKING_CATEGORIES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    TOP_N,
)

_LOGGER = logging.getLogger(__name__)


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


def _parse_rankings(html: str, category_key: str) -> dict[int, dict[str, Any]]:
    """Extract top-N ranking entries from a Danelfin ranking page HTML.

    Returns {rank: {ticker, company, ai_score, rating}}.
    Only the first TOP_N (5) free positions are parsed — Danelfin requires
    login for positions 6+.

    Handles two HTML formats emitted by Danelfin's Next.js RSC:
      • Rendered HTML: href="/stock/TICKER" or href="/etf/TICKER"
      • RSC JSON payload: \\"slug\\":\\"TICKER\\" (escaped JSON embedded in HTML)
    """
    cfg = RANKING_CATEGORIES[category_key]
    link_re: str = cfg["link_re"]

    # RSC JSON emits tickers as \"slug\":\"TICKER\" (literal backslash-quote).
    # This is the primary format for US stocks and ETFs on their ranking pages.
    _RSC_SLUG_RE = re.compile(r'\\"slug\\":\\"([A-Z0-9.]{1,12})\\"')

    results: dict[int, dict[str, Any]] = {}
    rank = 0

    for m in re.finditer(r"TitleCell_titleLine", html):
        chunk = html[m.start(): m.start() + 1200]

        # Locked rows (positions 6+) — stop immediately.
        # Both rendered HTML and RSC JSON use these markers.
        if "Lock Icon" in chunk or "Register for free" in chunk:
            break

        # 1. Try the category-specific link_re (works on rendered HTML sections).
        ticker_m = re.search(link_re, chunk)

        # 2. Fallback: RSC JSON slug format used by US/ETF ranking pages.
        if not ticker_m:
            ticker_m = _RSC_SLUG_RE.search(chunk)

        if not ticker_m:
            continue

        ticker = ticker_m.group(1).upper().rstrip("\\")

        # Company / ETF name.
        # Priority: title="..." attribute on TitleCell_subtitle (most reliable,
        # present in rendered HTML for both stocks and ETFs).
        company = ""
        title_m = re.search(
            r'TitleCell_subtitle[^>]+title="([^"]{2,80})"', chunk)
        if title_m:
            company = title_m.group(1).strip()
        else:
            sub = re.search(
                r'TitleCell_subtitle[^"]*"[^>]*>([^<]{2,80})<', chunk)
            if sub:
                company = sub.group(1).strip()
            else:
                spans = re.findall(r"<span[^>]*>([^<]{3,80})</span>", chunk)
                company = next(
                    (s.strip() for s in spans
                     if s.strip() and s.strip() != ticker and "Icon" not in s),
                    "",
                )

        # AI score — search a wider window because it follows the title cell.
        # EU/ETF pages use rendered HTML (aria-label needs ~7000+ chars).
        # US ranking page uses RSC JSON (doubly-escaped aria-label).
        wider = html[m.start(): m.start() + 10000]
        score_m = (
            re.search(r'aria-label="(\d+) out of 10"', wider)
            or re.search(r'\\"aria-label\\":\\"(\d+) out of 10\\"', wider)
        )
        ai_score = int(score_m.group(1)) if score_m else None

        rank += 1
        results[rank] = {
            "ticker": ticker,
            "company": company,
            "ai_score": ai_score,
            "rating": _derive_rating(ai_score),
            "rank": rank,
        }
        if rank >= TOP_N:
            break

    return results


class DanelfinRecommendationsCoordinator(DataUpdateCoordinator):
    """Fetch top-ranked stocks/ETFs from Danelfin ranking pages.

    Enabled categories are stored in the base config entry options.
    Returns {category_key: {rank: {...}}} after each refresh.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        enabled_categories: list[str],
        scan_hours: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self.enabled_categories = enabled_categories

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_recommendations",
            update_interval=timedelta(hours=scan_hours),
        )

    async def _async_update_data(self) -> dict[str, dict[int, dict[str, Any]]]:
        if not self.enabled_categories:
            return {}

        results: dict[str, dict[int, dict[str, Any]]] = {}
        connector = aiohttp.TCPConnector(ssl=True)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=REQUEST_HEADERS,
        ) as session:
            for cat_key in self.enabled_categories:
                cfg = RANKING_CATEGORIES.get(cat_key)
                if not cfg:
                    continue
                url: str = cfg["url"]
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        if resp.status != 200:
                            _LOGGER.warning(
                                "Danelfin recommendations: HTTP %s for %s",
                                resp.status,
                                cat_key,
                            )
                            continue
                        html = await resp.text()
                except aiohttp.ClientError as exc:
                    _LOGGER.error(
                        "Recommendations fetch error for %s: %s", cat_key, exc)
                    continue

                parsed = _parse_rankings(html, cat_key)
                results[cat_key] = parsed
                _LOGGER.info(
                    "Danelfin recommendations [%s]: fetched %d entries",
                    cat_key,
                    len(parsed),
                )

        if not results and self.enabled_categories:
            raise UpdateFailed(
                "Danelfin: failed to retrieve recommendations for any category."
            )

        return results
