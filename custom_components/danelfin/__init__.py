"""The Danelfin integration.

Architecture:
  1. One base entry (created on first install, no ticker) — sets up the integration.
  2. Each subsequent "Add entry" creates a ticker entry → device with 9 sensors.
  3. Delete a ticker entry to stop tracking that stock.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_TICKER, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import DanelfinCoordinator

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
    if entry.data.get("is_base"):
        # Base entry — integration installed, no sensors to create.
        return True

    ticker = entry.data[CONF_TICKER]
    coordinator = DanelfinCoordinator(hass, [ticker], DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.data.get("is_base"):
        return True

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
