"""Config flow for Danelfin integration.

Architecture:
  1. Add Integration → Danelfin → choose recommendation categories → installs base entry.
  2. Add entry → enter ticker + select market type → device with sensors created.
  3. Repeat step 2 for each additional ticker.
  4. Delete a ticker entry to stop tracking it.
  5. Options flow on base entry → enable / disable recommendation categories.

Update interval is fixed (Danelfin publishes once daily after US market close).
"""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow

try:
    from homeassistant.config_entries import ConfigFlowResult  # HA 2024.8+
except ImportError:
    # type: ignore[assignment]
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

import aiohttp

from homeassistant.core import callback

from .api import DanelfinApiClient, DanelfinApiError, DanelfinAuthError
from .const import (
    CONF_API_KEY,
    CONF_MARKET,
    CONF_REC_ETF,
    CONF_REC_EU,
    CONF_REC_US,
    CONF_SCAN_INTERVAL,
    CONF_TICKER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MARKET_ETF,
    MARKET_EU,
    MARKET_US,
)

# Allow letters, digits and dots (e.g. SAN.MC, BRK.B)
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.]{0,11}$")


def _validate_ticker(raw: str) -> str:
    """Normalise and validate a ticker symbol."""
    ticker = raw.strip().upper()
    if not ticker:
        raise vol.Invalid("ticker_empty")
    if not _TICKER_RE.match(ticker):
        raise vol.Invalid("ticker_invalid")
    return ticker


def _rec_schema(defaults: dict[str, bool]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_REC_EU, default=defaults.get(CONF_REC_EU, False)): bool,
            vol.Optional(CONF_REC_US, default=defaults.get(CONF_REC_US, False)): bool,
            vol.Optional(CONF_REC_ETF, default=defaults.get(CONF_REC_ETF, False)): bool,
        }
    )


def _base_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
            vol.Optional(CONF_REC_EU, default=defaults.get(CONF_REC_EU, False)): bool,
            vol.Optional(CONF_REC_US, default=defaults.get(CONF_REC_US, False)): bool,
            vol.Optional(CONF_REC_ETF, default=defaults.get(CONF_REC_ETF, False)): bool,
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_REC_EU, default=defaults.get(CONF_REC_EU, False)): bool,
            vol.Optional(CONF_REC_US, default=defaults.get(CONF_REC_US, False)): bool,
            vol.Optional(CONF_REC_ETF, default=defaults.get(CONF_REC_ETF, False)): bool,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
        }
    )


def _build_add_ticker_schema() -> vol.Schema:
    """Build the schema for the add_ticker step (deferred selector import)."""
    try:
        from homeassistant.helpers.selector import (  # noqa: PLC0415
            SelectSelector,
            SelectSelectorConfig,
            SelectSelectorMode,
        )

        selector_mode = getattr(SelectSelectorMode, "DROPDOWN", SelectSelectorMode.LIST)
        market_field: Any = SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"value": MARKET_US, "label": "US Stock"},
                    {"value": MARKET_EU, "label": "European Stock"},
                    {"value": MARKET_ETF, "label": "ETF"},
                ],
                mode=selector_mode,
            )
        )
    except Exception:  # noqa: BLE001
        market_field = vol.In([MARKET_US, MARKET_EU, MARKET_ETF])

    return vol.Schema(
        {
            vol.Required("ticker"): str,
            vol.Optional(CONF_MARKET, default=MARKET_US): market_field,
        }
    )


class DanelfinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: base entry (with recommendations) + one entry per ticker."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> "DanelfinOptionsFlow":
        return DanelfinOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial installation — choose recommendation categories."""
        if any(
            entry.data.get("is_base")
            for entry in self._async_current_entries()
        ):
            return await self.async_step_add_ticker()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.get(CONF_API_KEY, "")).strip()
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            if not api_key:
                errors["base"] = "api_key_required"
            else:
                try:
                    await self._async_validate_api_key(api_key)
                except DanelfinAuthError:
                    errors["base"] = "invalid_api_key"
                except DanelfinApiError:
                    errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title="Danelfin",
                    data={"is_base": True, CONF_API_KEY: api_key},
                    options={
                        CONF_REC_EU: user_input.get(CONF_REC_EU, False),
                        CONF_REC_US: user_input.get(CONF_REC_US, False),
                        CONF_REC_ETF: user_input.get(CONF_REC_ETF, False),
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema({}),
            errors=errors,
        )

    async def _async_validate_api_key(self, api_key: str) -> None:
        """Validate the API key by fetching a lightweight endpoint."""
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            client = DanelfinApiClient(api_key, session=session)
            await client.async_get_sectors()

    async def async_step_add_ticker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one ticker — shown for every subsequent Add entry click."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                ticker = _validate_ticker(user_input.get("ticker", ""))
            except vol.Invalid as exc:
                errors["ticker"] = str(exc)
            else:
                market = user_input.get(CONF_MARKET, MARKET_US)
                unique_id = f"{market}_{ticker}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = ticker if market == MARKET_US else f"{ticker} ({market.upper()})"
                return self.async_create_entry(
                    title=title,
                    data={CONF_TICKER: ticker, CONF_MARKET: market},
                )

        return self.async_show_form(
            step_id="add_ticker",
            data_schema=_build_add_ticker_schema(),
            errors=errors,
            description_placeholders={"example": "NVDA / SAN.MC / BUG"},
        )


class DanelfinOptionsFlow(OptionsFlow):
    """Options flow — enable / disable recommendation categories."""

    def __init__(self, config_entry: Any) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._entry.data.get("is_base"):
            # Ticker entries have no options to configure.
            return self.async_abort(reason="no_options")

        current = self._entry.options

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
        )
