"""Shared entity helpers for the Hisense integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import HiSenseAC, HiSenseDryer, HiSenseFridge, HiSenseWasher


class HisenseEntity(CoordinatorEntity[HisenseDataUpdateCoordinator]):
    """Base entity with refrigerator-specific offline handling.

    Refrigerators retain cached values after cloud read failures and become
    unavailable when explicitly offline. Their connectivity, refresh, and
    timestamp entities can opt out. Other devices use coordinator availability.
    """

    _attr_has_entity_name = True

    #: Keep the entity available when the device or the cloud is unreachable.
    _attr_available_offline: bool = False

    def __init__(
        self,
        coordinator: HisenseDataUpdateCoordinator,
        unique_suffix: str,
        object_suffix: str,
        icon: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        device_id = coordinator.client.device_id
        slugified_device_id = slugify(device_id)
        
        self._attr_unique_id = f"{unique_suffix}_{slugified_device_id}"
        self._attr_suggested_object_id = f"{object_suffix}_{slugified_device_id}"
        
        if icon:
            self._attr_icon = icon

    @property
    def client(self) -> HiSenseAC | HiSenseDryer | HiSenseFridge | HiSenseWasher:
        """Return the device API client."""
        return self.coordinator.client

    @property
    def available(self) -> bool:
        """Use the refrigerator online flag or standard coordinator availability."""
        if self.coordinator.device_type != "冰箱":
            return super().available
        if self._attr_available_offline:
            return True
        return self.status.get("online") is not False

    @property
    def status(self) -> dict[str, Any]:
        """Return the latest coordinated status."""
        return self.coordinator.data or self.client.get_status()

    @property
    def device_info(self):
        """Return Home Assistant device registry info."""
        device_type = self.coordinator.device_type
        device_name = getattr(self.client, "device_name", "")
        
        type_map = {
            "冰箱": ("hisense_fridge", "Hisense Fridge"),
            "洗衣机": ("hisense_washer", "Hisense Washer"),
            "干衣机": ("hisense_dryer", "Hisense Dryer"),
            "电视": ("hisense_tv", "Hisense TV"),
            "烤箱": ("hisense_oven", "Hisense Oven"),
            "洗碗机": ("hisense_dishwasher", "Hisense Dishwasher"),
            "热水器": ("hisense_water_heater", "Hisense Water Heater"),
            "油烟机": ("hisense_hood", "Hisense Hood"),
            "燃气灶": ("hisense_stove", "Hisense Gas Stove"),
            "除湿机": ("hisense_dehumidifier", "Hisense Dehumidifier"),
            "新风系统": ("hisense_fresh_air", "Hisense Fresh Air"),
            "酒柜": ("hisense_wine_cabinet", "Hisense Wine Cabinet"),
        }
        default_key, default_name = type_map.get(device_type, ("hisense_ac", "Hisense AC"))
        translation_key = default_key
        name = device_name if device_name else default_name

        return {
            "identifiers": {(DOMAIN, self.client.device_id)},
            "name": name,
            "translation_key": translation_key,
            "manufacturer": "Hisense",
            "model": device_name,
            "serial_number": self.client.device_id,
        }
