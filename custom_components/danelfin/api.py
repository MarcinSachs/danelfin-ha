from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

import aiohttp

from .const import (
    MARKET_ETF,
    MARKET_EU,
    MARKET_US,
    SENSOR_AI_SCORE,
    SENSOR_FUNDAMENTAL,
    SENSOR_TECHNICAL,
    SENSOR_SENTIMENT,
    SENSOR_RISK,
)

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://apirest.danelfin.com"
DEFAULT_FIELDS = "aiscore,fundamental,technical,sentiment,low_risk"

FIELD_TO_SENSOR_MAP: dict[str, str] = {
    "aiscore": SENSOR_AI_SCORE,
    "fundamental": SENSOR_FUNDAMENTAL,
    "technical": SENSOR_TECHNICAL,
    "sentiment": SENSOR_SENTIMENT,
    "low_risk": SENSOR_RISK,
}


class DanelfinApiError(Exception):
    """Base exception for Danelfin API errors."""


class DanelfinAuthError(DanelfinApiError):
    """Authentication failed (401/403)."""


class DanelfinRateLimitError(DanelfinApiError):
    """API rate limit exceeded (429)."""


class DanelfinServerError(DanelfinApiError):
    """Server-side error (5xx)."""


class DanelfinBadRequestError(DanelfinApiError):
    """Bad request (400)."""


class DanelfinApiClient:
    """Client for the Danelfin REST API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None) -> None:
        self._api_key = api_key
        self._session = session

    async def async_get_ranking(
        self,
        ticker: str | None = None,
        date: str | None = None,
        market: str = MARKET_US,
        asset: str | None = None,
        fields: str = DEFAULT_FIELDS,
    ) -> dict[str, dict[str, Any]]:
        """Fetch ranking data from /ranking and normalize the response."""
        params: dict[str, str] = {"fields": fields}

        if ticker:
            params["ticker"] = ticker

        # The API requires at least one of ticker or date for all markets.
        # When neither is supplied, default to the most recent weekday so
        # the API returns the latest available ranking instead of a 400/404.
        resolved_date = date
        if not resolved_date and not ticker:
            resolved_date = self._latest_weekday().isoformat()

        if resolved_date:
            params["date"] = resolved_date

        if market == MARKET_EU:
            params["market"] = "europe"
        elif market == MARKET_ETF:
            params["asset"] = "etf"
        elif asset:
            params["asset"] = asset

        raw = await self._request("/ranking", params=params)
        return self._parse_ranking_response(raw, requested_ticker=ticker)

    async def async_get_sectors(self) -> list[str]:
        """Fetch the list of available sectors."""
        raw = await self._request("/sectors")
        if not isinstance(raw, list):
            raise DanelfinApiError("Unexpected /sectors response format")
        return [item["sector"] for item in raw if isinstance(item, dict) and "sector" in item]

    async def async_get_sector(self, slug: str) -> dict[str, Any]:
        """Fetch historical scores for a given sector."""
        return await self._request(f"/sectors/{slug}")

    async def async_get_industries(self) -> list[str]:
        """Fetch the list of available industries."""
        raw = await self._request("/industries")
        if not isinstance(raw, list):
            raise DanelfinApiError("Unexpected /industries response format")
        return [item["industry"] for item in raw if isinstance(item, dict) and "industry" in item]

    async def async_get_industry(self, slug: str) -> dict[str, Any]:
        """Fetch historical scores for a given industry."""
        return await self._request(f"/industries/{slug}")

    async def _request(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{API_BASE_URL.rstrip('/')}{path}"
        headers = {
            "x-api-key": self._api_key,
            "Accept": "application/json",
        }

        if self._session is not None:
            return await self._request_with_session(self._session, url, headers, params)

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            return await self._request_with_session(session, url, headers, params)

    async def _request_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
        params: dict[str, str] | None,
    ) -> Any:
        _LOGGER.debug("Danelfin API request: %s params=%s", url, params)
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                content = await resp.text()
                response_method = getattr(resp, "method", "GET")
                response_url = getattr(resp, "url", url)
                response_headers = getattr(resp, "headers", {}) or {}
                _LOGGER.debug(
                    "Danelfin API response: %s %s status=%s body=%s",
                    response_method,
                    response_url,
                    resp.status,
                    content[:300],
                )

                if resp.status in (401, 403):
                    raise DanelfinAuthError(
                        f"Authentication failed (HTTP {resp.status})"
                    )
                if resp.status == 429:
                    retry_after = response_headers.get("Retry-After")
                    retry_info = f" Retry-After: {retry_after}." if retry_after else ""
                    raise DanelfinRateLimitError(
                        f"Danelfin API rate limit exceeded (HTTP 429).{retry_info}"
                    )
                if resp.status == 400:
                    raise DanelfinBadRequestError(
                        f"Bad request: HTTP 400. Response: {content}"
                    )
                if 500 <= resp.status < 600:
                    raise DanelfinServerError(
                        f"Danelfin server error: HTTP {resp.status}. Response: {content}"
                    )
                if resp.status != 200:
                    raise DanelfinApiError(
                        f"Danelfin API returned HTTP {resp.status}: {content}"
                    )

                try:
                    return await resp.json(content_type=None)
                except aiohttp.ContentTypeError as exc:
                    raise DanelfinApiError(
                        f"Failed to parse JSON from {url}: {exc}"
                    ) from exc
        except aiohttp.ClientError as exc:
            _LOGGER.debug("Danelfin aiohttp transport error", exc_info=exc)
            raise DanelfinApiError("Danelfin API request failed") from exc

    @staticmethod
    def _latest_weekday() -> _date:
        """Return the most recent completed weekday (Mon-Fri).

        Starts from yesterday so we avoid requesting data for a day whose
        market has not yet closed (API returns 404 for future/today's dates
        if the update has not been published yet).
        """
        from datetime import timedelta
        d = _date.today() - timedelta(days=1)
        while d.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
            d -= timedelta(days=1)
        return d

    @staticmethod
    def _is_date_key(key: str) -> bool:
        """Return True if *key* looks like an ISO date (YYYY-MM-DD)."""
        import re as _re  # noqa: PLC0415
        return bool(_re.match(r"^\d{4}-\d{2}-\d{2}$", key))

    def _parse_ranking_response(
        self, raw: Any, requested_ticker: str | None = None
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(raw, dict):
            raise DanelfinApiError("Unexpected ranking response format")

        # API returns {"<YYYY-MM-DD>": {scores}} (one or many dates) when a
        # ticker is requested without a date filter.  Pick the first key —
        # the API returns dates in descending order so that is the latest.
        if requested_ticker and all(self._is_date_key(k) for k in raw):
            latest_key = next(iter(raw))
            latest_value = raw[latest_key]
            if isinstance(latest_value, dict) and self._is_score_entry(latest_value):
                return {requested_ticker: self._normalize_score_entry(latest_value)}

        results: dict[str, dict[str, Any]] = {}
        for key, value in raw.items():
            if isinstance(value, dict) and self._is_score_entry(value):
                results[key] = self._normalize_score_entry(value)
            elif isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    if isinstance(inner_value, dict) and self._is_score_entry(inner_value):
                        results[inner_key] = self._normalize_score_entry(
                            inner_value)

        if not results:
            raise DanelfinApiError("Unable to parse ranking response")

        return results

    def _is_score_entry(self, value: dict[str, Any]) -> bool:
        return any(field in value for field in FIELD_TO_SENSOR_MAP)

    def _normalize_score_entry(self, raw_entry: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for source_field, sensor_key in FIELD_TO_SENSOR_MAP.items():
            if source_field in raw_entry:
                try:
                    normalized[sensor_key] = int(raw_entry[source_field])
                except (TypeError, ValueError):
                    normalized[sensor_key] = None

        normalized["rating"] = self._derive_rating(
            normalized.get(SENSOR_AI_SCORE))
        return normalized

    def _derive_rating(self, ai_score: int | None) -> str:
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
