"""Config flow for Danelfin integration.

Initial setup:
  Add Integration → Danelfin → (confirm, no ticker yet) → integration installed.

Managing tickers afterwards via Configure button:
  ┌─ Menu ──────────────────────┐
  │  ▶ Add stock ticker         │  → single text field → saves → reloads
  │  ▶ Remove stock ticker      │  → dropdown of current tickers → removes
  │  ▶ Change update interval   │  → number field
  └─────────────────────────────┘
"""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TICKERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_TICKER_RE = re.compile(r"^[A-Z0-9]{1,5}$")
_MIN_SCAN_HOURS = 1
_MAX_SCAN_HOURS = 24


def _validate_ticker(raw: str) -> str:
    """Normalise and validate a single ticker symbol."""
    ticker = raw.strip().upper()
    if not ticker:
        raise vol.Invalid("Enter a ticker symbol (e.g. NVDA)")
    if not _TICKER_RE.match(ticker):
        raise vol.Invalid(
            f"'{ticker}' is not a valid symbol. Use 1–5 uppercase letters."
        )
    return ticker


class DanelfinConfigFlow(ConfigFlow, domain=DOMAIN):
    """One-time setup: just installs the integration, no ticker needed yet."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        # Prevent installing twice.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Danelfin",
                data={
                    CONF_TICKERS: [],
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        # Empty form — one click to confirm installation.
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DanelfinOptionsFlow:
        return DanelfinOptionsFlow(config_entry)


class DanelfinOptionsFlow(OptionsFlow):
    """Options flow: add / remove individual tickers and change interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        # Work on a mutable copy so each sub-step sees the latest state.
        self._tickers: list[str] = list(
            config_entry.options.get(
                CONF_TICKERS,
                config_entry.data.get(CONF_TICKERS, []),
            )
        )
        self._scan_hours: int = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

    # ── Main menu ────────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        menu_options = ["add_ticker", "change_interval"]
        if self._tickers:
            menu_options.insert(1, "remove_ticker")

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    # ── Add ticker ───────────────────────────────────────────────────────────

    async def async_step_add_ticker(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                ticker = _validate_ticker(user_input.get("ticker", ""))
            except vol.Invalid as exc:
                errors["ticker"] = str(exc)
            else:
                if ticker in self._tickers:
                    errors["ticker"] = "already_tracked"
                else:
                    self._tickers.append(ticker)
                    return self._save()

        return self.async_show_form(
            step_id="add_ticker",
            data_schema=vol.Schema({vol.Required("ticker"): str}),
            errors=errors,
            description_placeholders={"example": "NVDA"},
        )

    # ── Remove ticker ────────────────────────────────────────────────────────

    async def async_step_remove_ticker(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            to_remove = user_input.get("ticker")
            self._tickers = [t for t in self._tickers if t != to_remove]
            return self._save()

        options = [
            SelectOptionDict(value=t, label=t) for t in self._tickers
        ]
        return self.async_show_form(
            step_id="remove_ticker",
            data_schema=vol.Schema(
                {
                    vol.Required("ticker"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    # ── Change interval ──────────────────────────────────────────────────────

    async def async_step_change_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._scan_hours = user_input[CONF_SCAN_INTERVAL]
            return self._save()

        return self.async_show_form(
            step_id="change_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=self._scan_hours): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=_MIN_SCAN_HOURS, max=_MAX_SCAN_HOURS),
                    )
                }
            ),
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _save(self) -> FlowResult:
        """Persist current state to options and reload the integration."""
        return self.async_create_entry(
            title="",
            data={
                CONF_TICKERS: self._tickers,
                CONF_SCAN_INTERVAL: self._scan_hours,
            },
        )


