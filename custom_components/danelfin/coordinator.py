"""Data coordinator for Danelfin integration.

Strategy:
- Fetch ticker score data from the official Danelfin REST API.
- Use a central DataUpdateCoordinator per ticker entry.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .api import (
    DanelfinApiClient,
    DanelfinApiError,
    DanelfinAuthError,
    DanelfinRateLimitError,
)
from .const import (
    DOMAIN,
    MARKET_US,
    REQUEST_TIMEOUT,
    SENSOR_AI_SCORE,
    SENSOR_RATING,
)

_LOGGER = logging.getLogger(__name__)


class DanelfinCoordinator(DataUpdateCoordinator):
    """Fetch Danelfin AI scores for all tickers in this config entry.

    One entry per ticker. Returns {TICKER: {sensor_key: value}} after each refresh.
    Uses the official Danelfin REST API and a single short-lived session per cycle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        tickers: list[str],
        scan_hours: int,
        api_key: str,
        market: str = MARKET_US,
    ) -> None:
        self.tickers: list[str] = [t.strip().upper() for t in tickers]
        self.market: str = market
        self.api_key: str = api_key

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

        if utcnow().weekday() >= 5 and self.last_update_success and self.data:
            _LOGGER.debug("Skipping Danelfin update on weekend")
            return self.data

        results: dict[str, dict[str, Any]] = {}
        connector = aiohttp.TCPConnector(ssl=True)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        ) as session:
            client = DanelfinApiClient(self.api_key, session=session)
            for ticker in self.tickers:
                try:
                    response = await client.async_get_ranking(
                        ticker=ticker,
                        market=self.market,
                    )
                except DanelfinRateLimitError:
                    _LOGGER.warning(
                        "Danelfin API rate-limited for %s. Consider increasing "
                        "the scan interval.",
                        ticker,
                    )
                    continue
                except DanelfinAuthError as exc:
                    raise UpdateFailed(
                        "Danelfin API authentication failed. Check your API key."
                    ) from exc
                except DanelfinApiError as exc:
                    _LOGGER.error("Danelfin API error for %s: %s", ticker, exc)
                    continue

                ticker_data = response.get(ticker)
                if not ticker_data:
                    _LOGGER.warning(
                        "Danelfin: no ranking data returned for %s.",
                        ticker,
                    )
                    continue

                ticker_data["market"] = self.market
                ticker_data["last_updated"] = utcnow().isoformat()

                if ticker_data.get(SENSOR_AI_SCORE) is None:
                    _LOGGER.warning(
                        "Danelfin: no AI Score returned for %s.",
                        ticker,
                    )

                results[ticker] = ticker_data
                _LOGGER.info(
                    "Danelfin %s: AI Score=%s, Rating=%s",
                    ticker,
                    ticker_data.get(SENSOR_AI_SCORE),
                    ticker_data.get(SENSOR_RATING),
                )

        if not results and self.tickers:
            raise UpdateFailed(
                "Danelfin: failed to retrieve data for any ticker. "
                "Check network connectivity or whether the site is blocking requests."
            )

        return results


class DanelfinApiHealthCoordinator(DataUpdateCoordinator):
    """Track Danelfin API connectivity status for the base config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        scan_hours: int,
        api_key: str,
    ) -> None:
        self.api_key = api_key

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_api_health",
            update_interval=timedelta(hours=scan_hours),
        )

    async def _async_update_data(self) -> dict[str, str | bool]:
        """Check API status without raising so the health sensor remains available."""
        connector = aiohttp.TCPConnector(ssl=True)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        ) as session:
            client = DanelfinApiClient(self.api_key, session=session)
            try:
                await client.async_get_sectors()
            except DanelfinAuthError as exc:
                return {
                    "status": "Authentication Failed",
                    "error": str(exc),
                    "last_checked": utcnow().isoformat(),
                    "healthy": False,
                }
            except DanelfinRateLimitError as exc:
                return {
                    "status": "Rate Limited",
                    "error": str(exc),
                    "last_checked": utcnow().isoformat(),
                    "healthy": False,
                }
            except DanelfinApiError as exc:
                return {
                    "status": "Connection Failed",
                    "error": str(exc),
                    "last_checked": utcnow().isoformat(),
                    "healthy": False,
                }

        return {
            "status": "Connected",
            "error": "",
            "last_checked": utcnow().isoformat(),
            "healthy": True,
        }
