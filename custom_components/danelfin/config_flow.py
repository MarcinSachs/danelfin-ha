"""Config flow for Danelfin integration.

Architecture:
  1. Add Integration → Danelfin → click Submit (no ticker needed) → installs base entry.
  2. Add entry → enter ticker → device with 9 sensors created.
  3. Repeat step 2 for each additional ticker.
  4. Delete a ticker entry to stop tracking it.

Update interval is fixed (Danelfin publishes once daily after US market close).
"""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_TICKER,
    DOMAIN,
)

_TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")


def _validate_ticker(raw: str) -> str:
    """Normalise and validate a ticker symbol."""
    ticker = raw.strip().upper()
    if not ticker:
        raise vol.Invalid("ticker_empty")
    if not _TICKER_RE.match(ticker):
        raise vol.Invalid("ticker_invalid")
    return ticker


class DanelfinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: empty install step + one entry per ticker."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initial installation — no ticker needed."""
        # If a base entry already exists, route directly to ticker step.
        if any(
            entry.data.get("is_base")
            for entry in self._async_current_entries()
        ):
            return await self.async_step_add_ticker()

        if user_input is not None:
            return self.async_create_entry(
                title="Danelfin",
                data={"is_base": True},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_add_ticker(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add one ticker — shown for every subsequent Add entry click."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                ticker = _validate_ticker(user_input.get("ticker", ""))
            except vol.Invalid as exc:
                errors["ticker"] = str(exc)
            else:
                await self.async_set_unique_id(ticker)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=ticker,
                    data={CONF_TICKER: ticker},
                )

        return self.async_show_form(
            step_id="add_ticker",
            data_schema=vol.Schema({vol.Required("ticker"): str}),
            errors=errors,
            description_placeholders={"example": "NVDA"},
        )
