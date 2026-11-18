import asyncio
import logging

from homeassistant.core import callback
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
    FAN_DIFFUSE,
    SWING_ON,
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, climate_limits_signal
from .entity import HisenseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [
        c for c in coordinators.values() if c.device_type == "空调"
    ]
    entities = [
        HisenseACClimate(coordinator)
        for coordinator in ac_coordinators
    ]
    async_add_entities(entities)


class HisenseACClimate(HisenseEntity, ClimateEntity):
    _attr_translation_key = "thermostat"

    def __init__(self, coordinator):
        super().__init__(coordinator, "climate", "climate")
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE |
            ClimateEntityFeature.SWING_MODE
        )
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_fan_modes = [
            FAN_AUTO,
            FAN_DIFFUSE,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
        ]
        self._attr_hvac_modes = [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ]
        self._attr_swing_modes = [
            SWING_OFF,
            SWING_ON,
            SWING_VERTICAL,
            SWING_HORIZONTAL,
            SWING_BOTH,
        ]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._hvac_mode_lookup = {
            0: HVACMode.FAN_ONLY,
            1: HVACMode.HEAT,
            2: HVACMode.COOL,
            3: HVACMode.DRY,
            4: HVACMode.AUTO,
        }
        self._hvac_mode_to_id = {
            HVACMode.FAN_ONLY: 0,
            HVACMode.HEAT: 1,
            HVACMode.COOL: 2,
            HVACMode.DRY: 3,
            HVACMode.AUTO: 4,
        }
        self._fan_mode_lookup = {
            1: FAN_DIFFUSE,
            2: FAN_LOW,
            3: FAN_MEDIUM,
            4: FAN_HIGH
        }
        self._fan_mode_to_id = {
            FAN_DIFFUSE: 1,
            FAN_LOW: 2,
            FAN_MEDIUM: 3,
            FAN_HIGH: 4
        }

    @property
    def min_temp(self):
        return float(self.client.climate_min_temp)

    @property
    def max_temp(self):
        return float(self.client.climate_max_temp)

    @property
    def native_current_temperature(self):
        return self.status.get("indoor_temperature")

    @property
    def current_humidity(self):
        return self.status.get("humidity")

    @property
    def native_target_temperature(self):
        return self.status.get("desired_temperature")

    @property
    def hvac_mode(self):
        power_on = self.status.get("power_on")
        if power_on is None:
            return None
        if not power_on:
            return HVACMode.OFF
        return self._hvac_mode_lookup.get(self.status.get("hvac_mode_id"))

    @property
    def fan_mode(self):
        if self.status.get("auto_wind"):
            return FAN_AUTO
        return self._fan_mode_lookup.get(self.status.get("fan_mode_id"))

    @property
    def swing_mode(self):
        v_swing = bool(self.status.get("up_down_wind_full_control"))
        h_swing = bool(self.status.get("left_right_wind_full_control"))
        if v_swing and h_swing:
            return SWING_BOTH
        if v_swing:
            return SWING_VERTICAL
        if h_swing:
            return SWING_HORIZONTAL
        return SWING_OFF

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                climate_limits_signal(self.client.device_id),
                self._handle_climate_limits_updated,
            )
        )

    @callback
    def _handle_climate_limits_updated(self, *_args):
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if not self.status.get("power_on"):
            raise HomeAssistantError("空调处于关机状态，无法调节温度")
        if self.hvac_mode == HVACMode.FAN_ONLY:
            raise HomeAssistantError("送风模式下无法调节温度")

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            if await self.client.set_temperature(int(temperature)):
                self.coordinator.async_update_from_client()
                return
            raise HomeAssistantError("Failed to set Hisense AC temperature")

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if not self.status.get("power_on"):
            raise HomeAssistantError("空调处于关机状态，无法调节风速")
        if fan_mode == FAN_AUTO:
            if await self.client.set_auto_wind(True):
                self.coordinator.async_update_from_client()
                return
            raise HomeAssistantError("Failed to set Hisense AC automatic wind")
        fan_id = self._fan_mode_to_id.get(fan_mode)
        if fan_id is None:
            raise HomeAssistantError(f"Unsupported Hisense AC fan mode: {fan_mode}")
        if await self.client.set_fan_mode(fan_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense AC fan mode")

    async def async_set_swing_mode(self, swing_mode):
        if swing_mode not in self._attr_swing_modes:
            raise HomeAssistantError(f"Unsupported Hisense AC swing mode: {swing_mode}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("空调处于关机状态，无法设置摆风")
        if swing_mode == SWING_OFF:
            await self.client.set_vertical_swing(False)
            await self.client.set_horizontal_swing(False)
        elif swing_mode == SWING_VERTICAL:
            await self.client.set_vertical_swing(True)
            await self.client.set_horizontal_swing(False)
        elif swing_mode == SWING_HORIZONTAL:
            await self.client.set_vertical_swing(False)
            await self.client.set_horizontal_swing(True)
        elif swing_mode in (SWING_BOTH, SWING_ON):
            await self.client.set_vertical_swing(True)
            await self.client.set_horizontal_swing(True)
        self.coordinator.async_update_from_client()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        hvac_id = self._hvac_mode_to_id.get(hvac_mode)
        if hvac_id is None:
            raise HomeAssistantError(f"Unsupported Hisense AC HVAC mode: {hvac_mode}")
        power_on = self.status.get("power_on", False)
        same_hvac = self.status.get("hvac_mode_id") == hvac_id

        # power on same hvac   -> set hvac (do nothing)
        # power on different hvac -> set hvac
        # power off same hvac -> turn on
        # power off different hvac -> turn on and set hvac
        if power_on:
            success = await self.client.set_hvac_mode(hvac_id)
        elif same_hvac:
            success = await self.client.turn_on()
        else:
            if not await self.client.turn_on():
                raise HomeAssistantError("Failed to turn on Hisense AC")
            await asyncio.sleep(4)
            success = await self.client.set_hvac_mode(hvac_id)
        if success:
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense AC HVAC mode")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC")
