"""Sensor platform for Danelfin integration.

One config entry manages all tickers. The coordinator returns
{TICKER: {sensor_key: value}}. Each ticker becomes a separate Device;
each metric for that ticker becomes a SensorEntity under that Device.

When the user adds a new ticker via the Options flow, the entry reloads
and this setup function re-runs — new sensor entities are created
automatically because their unique IDs are new.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_AI_SCORE,
    SENSOR_BEAT_MARKET_PROB,
    SENSOR_COMPANY_NAME,
    SENSOR_FUNDAMENTAL,
    SENSOR_PRICE,
    SENSOR_PRICE_CURRENCY,
    SENSOR_PROB_ADVANTAGE,
    SENSOR_RATING,
    SENSOR_RISK,
    SENSOR_SENTIMENT,
    SENSOR_TECHNICAL,
)
from .coordinator import DanelfinCoordinator


@dataclass(frozen=True, kw_only=True)
class DanelfinSensorEntityDescription(SensorEntityDescription):
    """Extended description that carries the data key used by the coordinator."""

    data_key: str


# One description per sensor type; each ticker gets its own instance of each
SENSOR_DESCRIPTIONS: tuple[DanelfinSensorEntityDescription, ...] = (
    DanelfinSensorEntityDescription(
        key=SENSOR_AI_SCORE,
        data_key=SENSOR_AI_SCORE,
        name="AI Score",
        icon="mdi:robot-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        suggested_display_precision=0,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_FUNDAMENTAL,
        data_key=SENSOR_FUNDAMENTAL,
        name="Fundamental Score",
        icon="mdi:chart-bar",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_TECHNICAL,
        data_key=SENSOR_TECHNICAL,
        name="Technical Score",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_SENTIMENT,
        data_key=SENSOR_SENTIMENT,
        name="Sentiment Score",
        icon="mdi:trending-up",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_RISK,
        data_key=SENSOR_RISK,
        name="Risk Score",
        icon="mdi:shield-alert-outline",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_RATING,
        data_key=SENSOR_RATING,
        name="Rating",
        icon="mdi:tag-outline",
        device_class=SensorDeviceClass.ENUM,
        options=["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Unknown"],
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_BEAT_MARKET_PROB,
        data_key=SENSOR_BEAT_MARKET_PROB,
        name="Probability of Beating Market",
        icon="mdi:percent-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_PROB_ADVANTAGE,
        data_key=SENSOR_PROB_ADVANTAGE,
        name="Probability Advantage",
        icon="mdi:delta",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_PRICE,
        data_key=SENSOR_PRICE,
        name="Price",
        icon="mdi:currency-usd",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    DanelfinSensorEntityDescription(
        key=SENSOR_COMPANY_NAME,
        data_key=SENSOR_COMPANY_NAME,
        name="Company Name",
        icon="mdi:office-building-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for all tickers currently in the config entry."""
    coordinator: DanelfinCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        DanelfinSensor(coordinator, ticker, description)
        for ticker in coordinator.tickers
        for description in SENSOR_DESCRIPTIONS
    )


class DanelfinSensor(CoordinatorEntity[DanelfinCoordinator], SensorEntity):
    """One metric sensor for one stock ticker."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DanelfinCoordinator,
        ticker: str,
        description: DanelfinSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description: DanelfinSensorEntityDescription = description
        self._ticker = ticker

        # Unique ID: danelfin_TICKER_metric  (stable across reloads)
        self._attr_unique_id = f"{DOMAIN}_{ticker}_{description.key}"

        # Each ticker = one Device in the UI
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, ticker)},
            name=f"Danelfin – {ticker}",
            manufacturer="Danelfin",
            model="AI Stock Analytics",
            configuration_url=f"https://danelfin.com/stock/{ticker}",
        )

    @property
    def available(self) -> bool:
        """Available when coordinator has an entry for this ticker (even partial data)."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._ticker in self.coordinator.data
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key == SENSOR_PRICE and self.available:
            return self.coordinator.data[self._ticker].get(SENSOR_PRICE_CURRENCY, "USD")
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        if not self.available:
            return None
        return self.coordinator.data[self._ticker].get(
            self.entity_description.data_key
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.available:
            return {}

        data = self.coordinator.data[self._ticker]
        attrs: dict[str, Any] = {"ticker": self._ticker}

        company = data.get(SENSOR_COMPANY_NAME)
        if company:
            attrs["company"] = company

        if self.entity_description.key == SENSOR_PRICE:
            attrs["currency"] = data.get(SENSOR_PRICE_CURRENCY, "USD")  # also visible as unit

        if self.entity_description.key == SENSOR_AI_SCORE:
            for key in (
                SENSOR_FUNDAMENTAL,
                SENSOR_TECHNICAL,
                SENSOR_SENTIMENT,
                SENSOR_RISK,
                SENSOR_RATING,
                SENSOR_BEAT_MARKET_PROB,
                SENSOR_PROB_ADVANTAGE,
            ):
                if key in data:
                    attrs[key] = data[key]

        return attrs
