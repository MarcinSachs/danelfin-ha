"""Coordinator for Danelfin top-ranking recommendation lists using the official API."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DanelfinApiClient, DanelfinApiError, DanelfinAuthError, DanelfinRateLimitError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RANKING_CATEGORIES,
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


class DanelfinRecommendationsCoordinator(DataUpdateCoordinator):
    """Fetch top-ranked stocks/ETFs from the official Danelfin ranking API."""

    def __init__(
        self,
        hass: HomeAssistant,
        enabled_categories: list[str],
        scan_hours: int = DEFAULT_SCAN_INTERVAL,
        api_key: str = "",
    ) -> None:
        self.enabled_categories = enabled_categories
        self.api_key = api_key

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
        ) as session:
            client = DanelfinApiClient(self.api_key, session=session)

            for cat_key in self.enabled_categories:
                cfg = RANKING_CATEGORIES.get(cat_key)
                if not cfg:
                    continue

                try:
                    response = await client.async_get_ranking(
                        market=cfg["market"],
                        asset=cfg.get("asset"),
                    )
                except DanelfinAuthError as exc:
                    raise UpdateFailed(
                        "Danelfin API authentication failed for recommendations."
                    ) from exc
                except DanelfinRateLimitError:
                    _LOGGER.warning(
                        "Danelfin API rate-limited while fetching recommendations for %s.",
                        cat_key,
                    )
                    continue
                except DanelfinApiError as exc:
                    _LOGGER.error(
                        "Danelfin recommendations API error for %s: %s",
                        cat_key,
                        exc,
                    )
                    continue

                sorted_items = sorted(
                    response.items(),
                    key=lambda item: (-(item[1].get("ai_score") or -1), item[0]),
                )
                entries: dict[int, dict[str, Any]] = {}
                rank = 0

                for ticker, data in sorted_items:
                    if rank >= TOP_N:
                        break
                    rank += 1
                    entries[rank] = {
                        "rank": rank,
                        "ticker": ticker,
                        "company": data.get("company_name", ""),
                        "ai_score": data.get("ai_score"),
                        "rating": data.get("rating", "Unknown"),
                    }

                results[cat_key] = entries
                _LOGGER.info(
                    "Danelfin recommendations [%s]: fetched %d entries",
                    cat_key,
                    len(entries),
                )

        if not results and self.enabled_categories:
            raise UpdateFailed(
                "Danelfin: failed to retrieve recommendations for any category."
            )

        return results
