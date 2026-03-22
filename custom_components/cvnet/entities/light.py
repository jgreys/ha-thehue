from __future__ import annotations
import logging
from typing import Any, List
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

FALLBACK_LIGHTS = [{"name": "거실2", "number": "2"}, {"name": "거실3", "number": "3"}]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    lights: List[dict] = []
    # Try to discover lights from the coordinator's light status data
    light_data = (coord.data or {}).get("lights") or {}
    body = light_data.get("body") if isinstance(light_data, dict) else None
    if isinstance(body, dict):
        for item in body.get("contents", []):
            try:
                num = str(item.get("number"))
                title = item.get("title") or f"Light {num}"
                lights.append({"name": title, "number": num})
            except Exception:
                continue
    if not lights:
        lights = FALLBACK_LIGHTS
    entities = [CvnetLight(coord, l) for l in lights]
    async_add_entities(entities, update_before_add=False)


class CvnetLight(CoordinatorEntity, LightEntity):
    """Light entity that syncs state from coordinator."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator: CvnetCoordinator, li: dict):
        super().__init__(coordinator)
        self._name = li["name"]
        self._number = str(li["number"])
        self._is_on = False
        self._attr_unique_id = f"cvnet_light_{self._number}_zone1"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_lights")}, name="Lights", manufacturer="CVNET")

    @property
    def name(self):
        return self._name

    @property
    def is_on(self) -> bool:
        return self._is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        lights_data = (self.coordinator.data or {}).get("lights", {})
        body = lights_data.get("body", {})
        for light in body.get("contents", []):
            if str(light.get("number")) == self._number:
                self._is_on = str(light.get("onoff", "0")) == "1"
                break

        self.async_write_ha_state()

    async def _async_set_light(self, onoff: str) -> None:
        body = {"request": "control", "number": self._number, "onoff": onoff, "brightness": "0", "zone": "1"}
        await self.coordinator.client.async_publish(address="18", body=body)
        self._is_on = onoff == "1"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any):
        await self._async_set_light("1")

    async def async_turn_off(self, **kwargs: Any):
        await self._async_set_light("0")
