
from __future__ import annotations

from typing import Any, Optional
import logging

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CvnetVisitorCamera(coord)])

class CvnetVisitorCamera(Camera):
    _attr_content_type = 'image/jpeg'
    _attr_name = "Visitor"
    # _attr_has_entity_name removed for simplicity

    def __init__(self, coordinator: CvnetCoordinator) -> None:
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = "cvnet_visitor_camera"
        # Use the same device as the sensor to avoid duplicate devices
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cvnet_visitors")},
            name="Visitors",
            manufacturer="CVNET"
        )
        self._unsubscribe = None
    
    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        await super().async_added_to_hass()
        
        def _handle_coordinator_update() -> None:
            """Handle updated data from the coordinator."""
            # Signal that image has changed
            self.async_write_ha_state()
        
        # Subscribe to coordinator updates
        self._unsubscribe = self.coordinator.async_add_listener(_handle_coordinator_update)
    
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from coordinator updates."""
        if self._unsubscribe:
            self._unsubscribe()
        await super().async_will_remove_from_hass()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        file_name = self.coordinator.get_visitor_selected()
        if not file_name and isinstance(self.coordinator.data, dict):
            items = (self.coordinator.data.get("vis") or {}).get("contents") if self.coordinator.data else None
            if items:
                file_name = items[0].get("file_name")
        # If still no file_name, try to prime the visitor list once on-demand
        if not file_name:
            try:
                await self.coordinator.async_prime_visitors()
                file_name = self.coordinator.get_visitor_selected()
                if not file_name and isinstance(self.coordinator.data, dict):
                    items = (self.coordinator.data.get("vis") or {}).get("contents") if self.coordinator.data else None
                    if items:
                        file_name = items[0].get("file_name")
            except Exception as ex:
                _LOGGER.debug("Prime visitors during camera fetch failed: %s", ex)
        if not file_name:
            vis_len = len((self.coordinator.data or {}).get("vis", {}).get("contents", []) if isinstance(self.coordinator.data, dict) else [])
            _LOGGER.error("No file_name available for visitor image fetch (visitor_count=%s).", vis_len)
            return None
        try:
            img = await self.coordinator.client.async_visitor_image_bytes(file_name)
            if img is None:
                _LOGGER.error(f"Image fetch returned None for file_name={file_name}")
            return img
        except Exception as e:
            _LOGGER.error(f"Exception during visitor image fetch for file_name={file_name}: {e}")
            return None
