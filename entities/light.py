from __future__ import annotations
import logging
from typing import Any, List
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    lights: List[dict] = []
    devs = (coord.data or {}).get("devices") or {}
    for item in devs.get("contents", []):
        try:
            num = str(item.get("number"))
            title = item.get("title") or f"Light {num}"
            lights.append({"name": title, "number": num})
        except Exception:
            continue
    if not lights:
        lights = [{"name":"거실2","number":"2"},{"name":"거실3","number":"3"}]
    entities = [CvnetLight(coord, l) for l in lights]
    async_add_entities(entities, update_before_add=False)

class CvnetLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator: CvnetCoordinator, li: dict):
        self.coordinator = coordinator
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

    async def async_turn_on(self, **kwargs: Any):
        username = getattr(self.coordinator.client, "_username", "homeassistant")
        body = {"id": username, "remote_addr": "127.0.0.1", "request": "control", "number": self._number, "onoff": "1", "brightness": "0", "zone": "1"}
        await self.coordinator.client.async_publish(address="18", body=body)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any):
        username = getattr(self.coordinator.client, "_username", "homeassistant")
        body = {"id": username, "remote_addr": "127.0.0.1", "request": "control", "number": self._number, "onoff": "0", "brightness": "0", "zone": "1"}
        await self.coordinator.client.async_publish(address="18", body=body)
        self._is_on = False
        self.async_write_ha_state()
