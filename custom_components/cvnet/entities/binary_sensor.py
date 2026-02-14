from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CvnetConnectionStatusSensor(coord, entry)], update_before_add=False)


class CvnetConnectionStatusSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating WebSocket connection health."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:lan-connect"
    _attr_name = "CVNET Connection Status"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connection_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_system")},
            name="CVNET System",
            manufacturer="CVNET",
        )

    @property
    def is_on(self) -> bool:
        """Return True if WebSocket connection is healthy."""
        return self.coordinator.client._is_ws_healthy()

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional connection info."""
        client = self.coordinator.client
        return {
            "has_credentials": bool(getattr(client, "_creds", None)),
            "session_expired": client._is_session_expired() if hasattr(client, "_is_session_expired") else None,
            "websocket_connected": self.coordinator.client._is_ws_healthy(),
        }
