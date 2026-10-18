"""Shared entity helpers for the Hisense integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import HiSenseAC, HiSenseDryer, HiSenseFridge, HiSenseWasher


class HisenseEntity(CoordinatorEntity[HisenseDataUpdateCoordinator]):
    """Base entity for one Hisense device.

    Availability has exactly one gate: the device's own ``onlineStatus``. A
    failed cloud read deliberately does *not* make entities unavailable — HA
    then keeps the last known values on screen, which is far more useful than a
    wall of "unavailable" entries.

    Models that never report ``onlineStatus`` have no such key, and unknown is
    not "offline", so they are unaffected.

    Entities that report *about* connectivity — the diagnostic ``connectivity``
    binary sensor and the manual refresh button — set
    :attr:`_attr_available_offline` so they stay usable and can actually show
    the offline state instead of going unavailable themselves.
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
        """Return False only when the cloud says the device is offline.

        ``online`` is ``None`` both for "not read yet" and for models that never
        report ``onlineStatus``; unknown must not be treated as offline,
        otherwise such models would lose every entity.
        """
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
        
        if device_type == "冰箱":
            translation_key = "hisense_fridge"
            name = device_name if device_name else "Hisense Fridge"
        elif device_type == "洗衣机":
            translation_key = "hisense_washer"
            name = device_name if device_name else "Hisense Washer"
        elif device_type == "干衣机":
            translation_key = "hisense_dryer"
            name = device_name if device_name else "Hisense Dryer"
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
