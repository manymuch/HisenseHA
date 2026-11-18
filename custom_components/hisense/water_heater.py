"""Hisense Water Heater integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HisenseEntity
from .pyhisenseapi import (
    WATER_HEATER_MODES,
    WATER_HEATER_MODE_TO_ID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense water heater entities based on a config entry."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    wh_coordinators = [c for c in coordinators.values() if c.device_type == "热水器"]
    async_add_entities(
        HisenseWaterHeaterEntity(coordinator) for coordinator in wh_coordinators
    )


class HisenseWaterHeaterEntity(HisenseEntity, WaterHeaterEntity):
    """Hisense Water Heater Entity."""

    _attr_translation_key = "water_heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 30.0
    _attr_max_temp = 75.0
    _attr_target_temperature_step = 1.0
    _attr_operation_list = [STATE_OFF] + list(WATER_HEATER_MODES.values())

    def __init__(self, coordinator) -> None:
        """Initialize the water heater entity."""
        super().__init__(coordinator, "water_heater", "water_heater")
        features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )
        if hasattr(WaterHeaterEntityFeature, "ON_OFF"):
            features |= WaterHeaterEntityFeature.ON_OFF
        self._attr_supported_features = features
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        if not self.status.get("power_on"):
            return STATE_OFF

        mode = self.status.get("work_mode")
        if mode is None:
            return None
        return WATER_HEATER_MODES.get(mode, f"模式{mode}")

    @property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        val = self.status.get("current_temperature") or self.status.get("real_temperature")
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature for older HA versions."""
        return self.native_current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        val = self.status.get("target_temperature")
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature for older HA versions."""
        return self.native_target_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attrs: dict[str, Any] = {}
        if (heat_status := self.status.get("heat_status")) is not None:
            attrs["heat_status"] = heat_status
        if (heat_finished := self.status.get("heat_finished")) is not None:
            attrs["heat_finished"] = heat_finished
        if (quantity := self.status.get("hot_water_quantity")) is not None:
            attrs["hot_water_quantity"] = quantity
        if (faults := self.status.get("faults")) is not None:
            attrs["faults"] = faults
        if (is_gas := self.status.get("is_gas")) is not None:
            attrs["is_gas"] = is_gas
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = int(round(kwargs[ATTR_TEMPERATURE]))
            if await self.client.set_temperature(temp):
                self.coordinator.async_update_from_client()
                return
            raise HomeAssistantError(f"设置热水器水温 {temp}℃ 失败")

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        if operation_mode == STATE_OFF or str(operation_mode).lower() == "off":
            await self.async_turn_off()
            return

        mode_id = WATER_HEATER_MODE_TO_ID.get(operation_mode)
        if mode_id is not None:
            if not self.status.get("power_on"):
                await self.client.turn_on()
            if await self.client.set_mode(mode_id):
                self.coordinator.async_update_from_client()
                return
            raise HomeAssistantError(f"设置热水器模式 {operation_mode} 失败")
        raise HomeAssistantError(f"不支持的热水器模式: {operation_mode}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the water heater."""
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("开启海信热水器失败")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the water heater."""
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("关闭海信热水器失败")
