from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CvnetCarPrevPageButton(coord, entry),
        CvnetCarNextPageButton(coord, entry),
        CvnetVisitorPrevPageButton(coord, entry),
        CvnetVisitorNextPageButton(coord, entry),
    ], update_before_add=False)
class _BaseVisitorButton(ButtonEntity):
    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry, name: str, uid: str) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cvnet_visitors")},
            name="Visitors",
            manufacturer="CVNET",
        )

class CvnetVisitorPrevPageButton(_BaseVisitorButton):
    _attr_icon = "mdi:page-previous"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Visitor Prev Page", "visitor_prev")

    async def async_press(self) -> None:
        await self.coordinator.async_visitor_prev_page()

class CvnetVisitorNextPageButton(_BaseVisitorButton):
    _attr_icon = "mdi:page-next"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Visitor Next Page", "visitor_next")

    async def async_press(self) -> None:
        await self.coordinator.async_visitor_next_page()

class _BaseCarButton(ButtonEntity):
    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry, name: str, uid: str) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_car")},
            name="Car Entrance",
            manufacturer="CVNET",
        )

class CvnetCarPrevPageButton(_BaseCarButton):
    _attr_icon = "mdi:page-previous"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Car Prev Page", "car_prev")

    async def async_press(self) -> None:
        await self.coordinator.async_car_prev_page()

class CvnetCarNextPageButton(_BaseCarButton):
    _attr_icon = "mdi:page-next"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Car Next Page", "car_next")

    async def async_press(self) -> None:
        await self.coordinator.async_car_next_page()
