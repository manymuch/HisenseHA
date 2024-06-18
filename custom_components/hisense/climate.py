import asyncio
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_DIFFUSE,
    SWING_ON,
    SWING_OFF,
    SWING_HORIZONTAL,
    SWING_VERTICAL
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]
    entity = HisenseACClimate(api)
    async_add_entities([entity], True)


class HisenseACClimate(ClimateEntity):
    def __init__(self, api):
        self._api = api
        self._attr_name = f"Hisense AC"
        self._attr_unique_id = f"{api.device_id}_climate"
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE |
            ClimateEntityFeature.SWING_MODE
        )
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_fan_modes = [FAN_AUTO, FAN_DIFFUSE,
                                FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_hvac_modes = [
            HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
        self._attr_swing_modes = [
            SWING_ON, SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL]
        self._attr_swing_mode = SWING_OFF
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature = None
        self._attr_current_temperature = None
        self._attr_min_temp = 16
        self._attr_max_temp = 32
        self._attr_is_on = False
        self._attr_hvac_mode = None
        self._attr_fan_mode = None
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
            0: FAN_AUTO,
            1: FAN_DIFFUSE,
            2: FAN_LOW,
            3: FAN_MEDIUM,
            4: FAN_HIGH
        }
        self._fan_mode_to_id = {
            FAN_AUTO: 0,
            FAN_DIFFUSE: 1,
            FAN_LOW: 2,
            FAN_MEDIUM: 3,
            FAN_HIGH: 4
        }
        self._swing_mode_lookup = {
            0: SWING_OFF,
            1: SWING_ON,
            2: SWING_HORIZONTAL,
            3: SWING_VERTICAL
        }
        self._swing_mode_to_id = {
            SWING_OFF: 0,
            SWING_ON: 1,
            SWING_HORIZONTAL: 2,
            SWING_VERTICAL: 3
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "manufacturer": "Hisense",
        }

    async def async_update(self):
        status = self._api.get_status()
        self._attr_is_on = status.get("power_on")
        self._attr_current_temperature = status.get("indoor_temperature")
        self._attr_target_temperature = status.get("desired_temperature")
        if self._attr_is_on:
            self._attr_hvac_mode = self._hvac_mode_lookup[status.get(
                "hvac_mode_id", 4)]
        else:
            self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = self._fan_mode_lookup[status.get(
            "fan_mode_id", 0)]
        self._attr_swing_mode = self._swing_mode_lookup[status.get(
            "swing_mode_id", 0)]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if not self._api.get_status().get("power_on"):
            _LOGGER.error("Cannot set temperature when power is off")
            return
        if self._attr_hvac_mode == HVACMode.FAN_ONLY:
            _LOGGER.error("Cannot set temperature in 'Fan Only' mode")
            return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            # Convert temperature to Celsius if necessary
            unit = self.hass.config.units.temperature_unit
            if unit == UnitOfTemperature.FAHRENHEIT:
                temperature = temperature * 9 / 5 + 32
            # Now, temperature is guaranteed to be in Celsius
            await self._api.send_logic_command(6, int(temperature))
            await self.async_update()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if not self._api.get_status().get("power_on"):
            _LOGGER.error("Cannot set fan mode when power is off")
            return
        fan_id = self._fan_mode_to_id.get(fan_mode)
        await self._api.send_logic_command(1, fan_id)
        self._attr_fan_mode = fan_mode
        await self.async_update()

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if not self._api.get_status().get("power_on"):
            _LOGGER.error("Cannot set swing mode when power is off")
            return
        if swing_mode in self._attr_swing_modes:
            swing_id = self._swing_mode_to_id.get(swing_mode)
            await self._api.send_logic_command(62, swing_id)
            # Update the entity's current swing mode
            self._attr_swing_mode = swing_mode
            # Notify Home Assistant that the entity's state has changed
            self.async_write_ha_state()
        else:
            _LOGGER.error("Unsupported swing mode: %s", swing_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        hvac_id = self._hvac_mode_to_id.get(hvac_mode)
        power_on = self._api.get_status().get("power_on", False)
        same_hvac = self._api.get_status().get("hvac_mode_id") == hvac_id

        # power on same hvac   -> set hvac (do nothing)
        # power on different hvac -> set hvac
        # power off same hvac -> turn on
        # power off different hvac -> turn on and set hvac
        if power_on:
            await self._api.send_logic_command(3, hvac_id)
            self._attr_hvac_mode = hvac_mode
        elif same_hvac:
            await self.async_turn_on()
        else:
            await self.async_turn_on()
            await asyncio.sleep(4)
            await self._api.send_logic_command(3, hvac_id)
            self._attr_hvac_mode = hvac_mode
        await self.async_update()

    async def async_turn_on(self):
        await self._api.turn_on()
        self._attr_is_on = True
        await self.async_update()

    async def async_turn_off(self):
        await self._api.turn_off()
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_is_on = False
        await self.async_update()
