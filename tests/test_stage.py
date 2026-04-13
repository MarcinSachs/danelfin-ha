"""Unit tests for Stage 3: entity refactoring and API data mapping."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
COMP_DIR = ROOT / "custom_components" / "danelfin"
PKG = "custom_components.danelfin"

# Stub Home Assistant dependencies used by the integration modules.
if "homeassistant" not in sys.modules:
    sys.modules["homeassistant"] = types.ModuleType("homeassistant")
if "homeassistant.core" not in sys.modules:
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    sys.modules["homeassistant.core"] = core
if "homeassistant.config_entries" not in sys.modules:
    config_entries = types.ModuleType("homeassistant.config_entries")
    class ConfigEntry:
        pass
    config_entries.ConfigEntry = ConfigEntry
    sys.modules["homeassistant.config_entries"] = config_entries
if "homeassistant.helpers" not in sys.modules:
    sys.modules["homeassistant.helpers"] = types.ModuleType("homeassistant.helpers")
if "homeassistant.helpers.update_coordinator" not in sys.modules:
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    class DataUpdateCoordinator:
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

    class UpdateFailed(Exception):
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item: Any) -> type:
            return cls

    setattr(update_coordinator, "DataUpdateCoordinator", DataUpdateCoordinator)
    setattr(update_coordinator, "UpdateFailed", UpdateFailed)
    setattr(update_coordinator, "CoordinatorEntity", CoordinatorEntity)
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
if "homeassistant.util" not in sys.modules:
    util = types.ModuleType("homeassistant.util")
    sys.modules["homeassistant.util"] = util
if "homeassistant.util.dt" not in sys.modules:
    util_dt = types.ModuleType("homeassistant.util.dt")
    from datetime import datetime, timezone
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)
    util_dt.utcnow = utcnow
    sys.modules["homeassistant.util.dt"] = util_dt
if "homeassistant.components.sensor" not in sys.modules:
    sensor_mod = types.ModuleType("homeassistant.components.sensor")
    class SensorEntity:
        pass
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class SensorEntityDescription:
        key: str | None = None
        data_key: str | None = None
        name: str | None = None
        icon: str | None = None
        state_class: Any = None
        native_unit_of_measurement: Any = None
        suggested_display_precision: Any = None
        device_class: Any = None
        options: Any = None

    class SensorDeviceClass:
        ENUM = "enum"

    class SensorStateClass:
        MEASUREMENT = "measurement"
    setattr(sensor_mod, "SensorEntity", SensorEntity)
    setattr(sensor_mod, "SensorEntityDescription", SensorEntityDescription)
    setattr(sensor_mod, "SensorDeviceClass", SensorDeviceClass)
    setattr(sensor_mod, "SensorStateClass", SensorStateClass)
    sys.modules["homeassistant.components.sensor"] = sensor_mod
if "homeassistant.const" not in sys.modules:
    const_mod = types.ModuleType("homeassistant.const")
    setattr(const_mod, "PERCENTAGE", "%")
    sys.modules["homeassistant.const"] = const_mod
if "homeassistant.helpers.device_registry" not in sys.modules:
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    class DeviceInfo(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(kwargs)
    class DeviceEntryType:
        SERVICE = "service"
    setattr(device_registry, "DeviceInfo", DeviceInfo)
    setattr(device_registry, "DeviceEntryType", DeviceEntryType)
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
if "homeassistant.helpers.entity_platform" not in sys.modules:
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    AddEntitiesCallback = object
    setattr(entity_platform, "AddEntitiesCallback", AddEntitiesCallback)
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
aiohttp = types.ModuleType("aiohttp")
class ClientTimeout:
    def __init__(self, total: int | None = None) -> None:
        self.total = total
class ClientSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
    async def __aenter__(self) -> "ClientSession":
        return self
    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False
    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
class ContentTypeError(Exception):
    pass
class ClientError(Exception):
    pass
class TCPConnector:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
setattr(aiohttp, "ClientTimeout", ClientTimeout)
setattr(aiohttp, "ClientSession", ClientSession)
setattr(aiohttp, "ContentTypeError", ContentTypeError)
setattr(aiohttp, "ClientError", ClientError)
setattr(aiohttp, "TCPConnector", TCPConnector)
sys.modules["aiohttp"] = aiohttp

# Create package modules so relative imports work.
_pkg_mod = types.ModuleType(PKG)
_pkg_mod.__path__ = [str(COMP_DIR)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules[PKG] = _pkg_mod


def _load_pkg_module(name: str):
    full_name = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(
        full_name,
        COMP_DIR / f"{name}.py",
        submodule_search_locations=[str(COMP_DIR)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PKG
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod

const = _load_pkg_module("const")
sensor = _load_pkg_module("sensor")
coordinator = _load_pkg_module("coordinator")


def test_sensor_extra_state_attributes_includes_new_fields() -> None:
    data = {
        "ai_score": 9,
        "fundamental_score": 8,
        "technical_score": 7,
        "sentiment_score": 6,
        "risk_score": 5,
        "rating": "Buy",
        "beat_market_probability": 12.34,
        "probability_advantage": 4.56,
        "price": 123.45,
        "price_currency": "USD",
        "company_name": "Test Company",
        "market": "us",
        "last_updated": "2026-04-13T12:00:00+00:00",
    }

    class FakeCoordinator:
        def __init__(self, data: dict[str, dict[str, Any]]) -> None:
            self.last_update_success = True
            self.data = data

    fake_coordinator = FakeCoordinator({"NVDA": data})
    description = next(
        d for d in sensor.SENSOR_DESCRIPTIONS if d.key == const.SENSOR_AI_SCORE
    )
    entity = sensor.DanelfinSensor(fake_coordinator, "NVDA", description)

    attrs = entity.extra_state_attributes

    assert attrs["ticker"] == "NVDA"
    assert attrs["company"] == "Test Company"
    assert attrs["last_updated"] == "2026-04-13T12:00:00+00:00"
    assert attrs["price"] == 123.45
    assert attrs["market"] == "us"
    assert attrs["fundamental_score"] == 8
    assert attrs["technical_score"] == 7
    assert attrs["sentiment_score"] == 6
    assert attrs["risk_score"] == 5
    assert attrs["rating"] == "Buy"
    assert attrs["beat_market_probability"] == 12.34
    assert attrs["probability_advantage"] == 4.56
    assert entity.native_value == 9


def test_api_health_sensor_reports_status() -> None:
    class FakeCoordinator:
        def __init__(self) -> None:
            self.last_update_success = True
            self.data = {
                "status": "Connected",
                "healthy": True,
                "last_checked": "2026-04-13T12:00:00+00:00",
                "error": "",
            }

    fake_coordinator = FakeCoordinator()
    entity = sensor.DanelfinApiHealthSensor(fake_coordinator)

    assert entity.native_value == "Connected"
    assert entity.extra_state_attributes["healthy"] is True
    assert entity.extra_state_attributes["last_checked"] == "2026-04-13T12:00:00+00:00"
    assert entity.extra_state_attributes["error"] == ""


def test_coordinator_adds_market_and_last_updated() -> None:
    fake = coordinator.DanelfinCoordinator(None, ["NVDA"], 8, "test-key", market="us")

    async def fake_get_ranking(self, ticker: str, market: str = "us", **kwargs: Any) -> dict[str, dict[str, Any]]:
        return {
            "NVDA": {
                "ai_score": 10,
                "fundamental_score": 9,
                "technical_score": 8,
                "sentiment_score": 7,
                "risk_score": 6,
                "rating": "Strong Buy",
                "price": 200.0,
                "price_currency": "USD",
                "company_name": "Test Company",
            }
        }

    coordinator.DanelfinApiClient.async_get_ranking = fake_get_ranking

    result = asyncio.run(fake._async_update_data())

    assert "NVDA" in result
    assert result["NVDA"]["market"] == "us"
    assert "last_updated" in result["NVDA"]
    assert result["NVDA"]["price"] == 200.0
    assert result["NVDA"]["company_name"] == "Test Company"
    assert result["NVDA"]["ai_score"] == 10
