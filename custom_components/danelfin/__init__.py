"""The Danelfin integration.

Architecture: ONE config entry for the whole integration.
Tickers are managed via the Options flow:
  Configure → Add stock   → adds one ticker → reloads → new device appears
  Configure → Remove stock → removes ticker  → reloads → device disappears

Tickers are persisted in entry.options[CONF_TICKERS].
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import CONF_SCAN_INTERVAL, CONF_TICKERS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import DanelfinCoordinator

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _get_tickers(entry: ConfigEntry) -> list[str]:
    """Return current ticker list from options (preferred) or data."""
    return entry.options.get(CONF_TICKERS, entry.data.get(CONF_TICKERS, []))


def _get_scan_hours(entry: ConfigEntry) -> int:
    return entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )


def _remove_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, active_tickers: list[str]
) -> None:
    """Delete entity registry entries for tickers no longer in the list.

    Unique ID format: danelfin_{TICKER}_{sensor_key}
    """
    registry = er.async_get(hass)
    active = {t.upper() for t in active_tickers}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        # parts: ["danelfin", "NVDA", "ai_score"]  (split maxsplit=2)
        parts = entity.unique_id.split("_", 2)
        if len(parts) >= 2 and parts[1] not in active:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the single Danelfin config entry."""
    tickers = _get_tickers(entry)
    scan_hours = _get_scan_hours(entry)

    coordinator = DanelfinCoordinator(hass, tickers, scan_hours)

    # First refresh is a no-op when tickers list is empty (fresh install).
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Clean up entities for tickers that were removed via options.
    _remove_stale_entities(hass, entry, tickers)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload whenever options change (ticker added/removed or interval changed)."""
    await hass.config_entries.async_reload(entry.entry_id)
