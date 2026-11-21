from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .ayla_eu import AylaError, FANS, MODES
from .entity import HisenseEntity


class EuropeanClimate(HisenseEntity, ClimateEntity):
    _attr_name = "Air conditioner"
    _attr_translation_key = "thermostat"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 32
    _attr_target_temperature_step = 1
    _attr_supported_features = (ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF |
                                ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE)
    _enable_turn_on_off_backwards_compatibility = False
    _attr_hvac_modes = [HVACMode.OFF] + [HVACMode(mode) for mode in MODES]
    _attr_fan_modes = list(FANS)

    def __init__(self, coordinator):
        super().__init__(coordinator, "eu_climate", "eu_climate")

    @property
    def current_temperature(self):
        return self.status.get("indoor_temperature")

    @property
    def target_temperature(self):
        return self.status.get("desired_temperature")

    @property
    def hvac_mode(self):
        return self.status.get("hvac_mode") if self.status.get("power_on") else HVACMode.OFF

    @property
    def fan_mode(self):
        return self.status.get("fan_mode")

    async def _command(self, setting, value):
        try:
            await self.client.command(setting, value)
        except AylaError:
            raise HomeAssistantError("European command failed; refresh state before retrying") from None
        self.coordinator.async_update_from_client()

    async def async_set_temperature(self, **kwargs):
        if "hvac_mode" in kwargs:
            await self.async_set_hvac_mode(kwargs["hvac_mode"])
        if ATTR_TEMPERATURE in kwargs:
            await self._command("temperature", kwargs[ATTR_TEMPERATURE])

    async def async_set_fan_mode(self, fan_mode):
        await self._command("fan", fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if hvac_mode not in MODES:
            raise HomeAssistantError("Unsupported European HVAC mode")
        await self._command("mode", hvac_mode)
        if not self.status.get("power_on"):
            await self.async_turn_on()

    async def async_turn_on(self):
        await self._command("power", True)

    async def async_turn_off(self):
        await self._command("power", False)


class EuropeanScreen(HisenseEntity, SwitchEntity):
    _attr_name = "Display"
    _attr_icon = "mdi:clock-digital"

    def __init__(self, coordinator):
        super().__init__(coordinator, "eu_screen", "eu_screen")

    @property
    def is_on(self):
        return self.status.get("screen_on")

    @property
    def available(self):
        prop = self.client.properties.get("t_backlight", {})
        return super().available and prop.get("read_only") is False and prop.get("direction") == "input"

    async def _set(self, value):
        try:
            await self.client.command("screen", value)
        except AylaError:
            raise HomeAssistantError("European display command failed") from None
        self.coordinator.async_update_from_client()

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)


class EuropeanRefresh(HisenseEntity, ButtonEntity):
    _attr_translation_key = "force_update"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "force_update_button", "force_update")

    async def async_press(self):
        await self.coordinator.async_request_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError("Failed to refresh European device status")
