"""Shared entity helpers for the Hisense integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import HiSenseAC, HiSenseFridge


class HisenseEntity(CoordinatorEntity[HisenseDataUpdateCoordinator]):
    """Base entity for one Hisense device."""

    _attr_has_entity_name = True

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
    def client(self) -> HiSenseAC | HiSenseFridge:
        """Return the device API client."""
        return self.coordinator.client

    @property
    def status(self) -> dict[str, Any]:
        """Return the latest coordinated status."""
        return self.coordinator.data or self.client.get_status()

    @property
    def device_info(self):
        """Return Home Assistant device registry info."""
        device_type = self.coordinator.device_type
        device_name = getattr(self.client, "device_name", "")
        
        if device_type == "冰箱":
            translation_key = "hisense_fridge"
            name = device_name if device_name else "Hisense Fridge"
        else:
            translation_key = "hisense_ac"
            name = device_name if device_name else "Hisense AC"

        return {
            "identifiers": {(DOMAIN, self.client.device_id)},
            "name": name,
            "translation_key": translation_key,
            "manufacturer": "Hisense",
            "model": device_name,
            "serial_number": self.client.device_id,
        }
