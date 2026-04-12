"""The Danelfin integration.

Architecture:
  1. One base entry (created on first install, no ticker) — sets up the integration.
     Its options control which recommendation categories are tracked.
  2. Each subsequent "Add entry" creates a ticker entry → device with sensors.
  3. Delete a ticker entry to stop tracking that stock.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MARKET,
    CONF_REC_ETF,
    CONF_REC_EU,
    CONF_REC_US,
    CONF_TICKER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MARKET_US,
    RANKING_CATEGORIES,
)
from .coordinator import DanelfinCoordinator
from .recommendations import DanelfinRecommendationsCoordinator

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate v1 (all-in-one entry) to v2 (per-ticker entries)."""
    if entry.version == 1:
        old_tickers: list[str] = entry.data.get("tickers", [])
        if len(old_tickers) == 1:
            hass.config_entries.async_update_entry(
                entry,
                data={CONF_TICKER: old_tickers[0]},
                version=2,
            )
            return True
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Danelfin config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data.get("is_base"):
        # Base entry — set up the recommendations coordinator if any category enabled.
        options = entry.options
        enabled_cats = [
            cat for cat in (CONF_REC_EU, CONF_REC_US, CONF_REC_ETF)
            if options.get(cat, False)
        ]
        if not enabled_cats:
            # Listen for options changes so sensors appear after the user enables categories.
            entry.async_on_unload(
                entry.add_update_listener(_async_entry_updated))
            return True

        rec_coordinator = DanelfinRecommendationsCoordinator(
            hass, enabled_cats, DEFAULT_SCAN_INTERVAL
        )
        await rec_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = rec_coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
        return True

    ticker = entry.data[CONF_TICKER]
    market = entry.data.get(CONF_MARKET, MARKET_US)
    coordinator = DanelfinCoordinator(
        hass, [ticker], DEFAULT_SCAN_INTERVAL, market)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when the user changes options (e.g. toggles a category)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not hass.data[DOMAIN].get(entry.entry_id):
        # Base entry with no coordinator (no categories enabled) or already unloaded.
        return True

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
