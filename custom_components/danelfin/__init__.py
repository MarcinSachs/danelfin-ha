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
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MARKET_US,
    RANKING_CATEGORIES,
)
from .coordinator import (
    DanelfinApiHealthCoordinator,
    DanelfinCoordinator,
)
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
        # Base entry — always create an API health coordinator, and optionally
        # create a recommendations coordinator for enabled categories.
        options = entry.options
        enabled_cats = [
            cat for cat in (CONF_REC_EU, CONF_REC_US, CONF_REC_ETF)
            if options.get(cat, False)
        ]
        scan_hours = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        health_coordinator = DanelfinApiHealthCoordinator(
            hass, scan_hours, entry.data.get(CONF_API_KEY, "")
        )
        await health_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = health_coordinator

        if enabled_cats:
            rec_coordinator = DanelfinRecommendationsCoordinator(
                hass,
                enabled_cats,
                scan_hours,
                entry.data.get(CONF_API_KEY, ""),
            )
            await rec_coordinator.async_config_entry_first_refresh()
            hass.data[DOMAIN][f"{entry.entry_id}_rec"] = rec_coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
        return True

    ticker = entry.data[CONF_TICKER]
    market = entry.data.get(CONF_MARKET, MARKET_US)
    base_entry = _find_base_entry(hass)
    if not base_entry:
        return False
    api_key = base_entry.data.get(CONF_API_KEY)
    if not api_key:
        return False
    scan_hours = base_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = DanelfinCoordinator(
        hass, [ticker], scan_hours, api_key, market)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _find_base_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the base config entry that contains global settings."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("is_base"):
            return entry
    return None


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when the user changes options.

    For the base entry, reload all ticker entries as well so they pick up
    changes to the global API key or scan interval.
    """
    await hass.config_entries.async_reload(entry.entry_id)

    if entry.data.get("is_base"):
        for other_entry in hass.config_entries.async_entries(DOMAIN):
            if other_entry.entry_id == entry.entry_id:
                continue
            await hass.config_entries.async_reload(other_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not hass.data[DOMAIN].get(entry.entry_id):
        return True

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_rec", None)
    return unloaded
