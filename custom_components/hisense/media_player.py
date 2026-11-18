"""Hisense TV Media Player platform."""
from __future__ import annotations

import logging
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HisenseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense TV media players from config entry."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    tv_coordinators = [
        c for c in coordinators.values()
        if getattr(c, "device_type", None) == "电视"
    ]
    if tv_coordinators:
        async_add_entities([HisenseTVMediaPlayer(c) for c in tv_coordinators])


class HisenseTVMediaPlayer(HisenseEntity, MediaPlayerEntity):
    """Representation of a Hisense TV media player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_translation_key = "tv_media_player"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "tv", "tv")
        self._attr_name = None  # Use device name

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the TV."""
        if not self.status.get("online", True):
            return MediaPlayerState.OFF
        if self.status.get("power_on"):
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self.status.get("is_volume_muted")

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        vol = self.status.get("volume")
        if vol is not None:
            return float(vol) / 100.0
        return None

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.status.get("source")

    async def async_turn_on(self) -> None:
        """Turn the TV on."""
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense TV")

    async def async_turn_off(self) -> None:
        """Turn the TV off."""
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense TV")

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        if await self.client.volume_up():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to increase Hisense TV volume")

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        if await self.client.volume_down():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to decrease Hisense TV volume")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if await self.client.mute(mute):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense TV mute")
