
from __future__ import annotations

import logging
from typing import List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CvnetVisitorSelect(coord, entry),
        CvnetCarRowsSelect(coord, entry),
        CvnetVisitorRowsSelect(coord, entry)
    ])
class CvnetVisitorRowsSelect(SelectEntity):
    _attr_icon = "mdi:format-list-numbered"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = "Visitor Rows"
        self._attr_unique_id = f"{entry.entry_id}_visitor_rows"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cvnet_visitors")},
            name="Visitors",
            manufacturer="CVNET",
        )

    @property
    def options(self):
        return ["5", "10", "14", "20"]

    @property
    def current_option(self):
        return str(self.coordinator.visitor_state().get("rows"))

    async def async_select_option(self, option: str) -> None:
        try:
            rows = int(option)
        except Exception:
            rows = 5
        await self.coordinator.async_visitor_set_rows(rows)

class CvnetVisitorSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Visitor Snapshot"
    _attr_has_entity_name = True
    _attr_icon = "mdi:camera-image"
    _attr_unique_id: str

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_visitor_select"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "cvnet_visitors")}, name="Visitors", manufacturer="CVNET")

    @property
    def options(self) -> List[str]:
        opts = self.coordinator.visitor_options()
        return opts if opts else ["(no snapshots)"]

    @property
    def current_option(self) -> Optional[str]:
        return self.coordinator.get_visitor_selected() or "(no snapshots)"

    async def async_select_option(self, option: str) -> None:
        # Ignore placeholder
        if option == "(no snapshots)":
            return
        self.coordinator.set_visitor_selected(option)
        await self.async_update_ha_state(True)


class CvnetCarRowsSelect(SelectEntity):
    _attr_icon = "mdi:format-list-numbered"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = "Car Rows"
        self._attr_unique_id = f"{entry.entry_id}_car_rows"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_car")},
            name="Car Entrance",
            manufacturer="CVNET",
        )

    @property
    def options(self):
        return ["5", "10", "14", "20"]

    @property
    def current_option(self):
        return str(self.coordinator.car_state().get("rows"))

    async def async_select_option(self, option: str) -> None:
        try:
            rows = int(option)
        except Exception:
            rows = 5
        await self.coordinator.async_car_set_rows(rows)
