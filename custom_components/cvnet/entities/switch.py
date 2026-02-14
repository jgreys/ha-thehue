from __future__ import annotations
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CvnetAllLightsSwitch(coord)], update_before_add=False)

class CvnetAllLightsSwitch(SwitchEntity):
    def __init__(self, coordinator: CvnetCoordinator):
        self.coordinator = coordinator
        self._attr_name = "All Lights"
        self._attr_unique_id = "cvnet_all_lights"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_lights")}, name="Lights", manufacturer="CVNET")

    async def async_turn_on(self, **kwargs):
        username = getattr(self.coordinator.client, "_username", "homeassistant")
        body = {"id": username, "remote_addr": "127.0.0.1", "request": "control_all", "onoff": "1", "brightness": "0", "zone": "0"}
        await self.coordinator.client.async_publish(address="18", body=body)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        username = getattr(self.coordinator.client, "_username", "homeassistant")
        body = {"id": username, "remote_addr": "127.0.0.1", "request": "control_all", "onoff": "0", "brightness": "0", "zone": "0"}
        await self.coordinator.client.async_publish(address="18", body=body)
        self._attr_is_on = False
        self.async_write_ha_state()
