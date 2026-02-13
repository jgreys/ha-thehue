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
        CvnetGasValveCloseButton(coord, entry),
        CvnetHeatingAllOnButton(coord, entry),
        CvnetHeatingAllOffButton(coord, entry),
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


class _BaseSystemButton(ButtonEntity):
    """Base class for system-level buttons (gas valve, heating controls)."""

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry, name: str, uid: str) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_system")},
            name="CVNET System",
            manufacturer="CVNET",
        )


class CvnetGasValveCloseButton(_BaseSystemButton):
    """Button to close the gas valve. Opening requires physical access for safety."""

    _attr_icon = "mdi:valve-closed"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Close Gas Valve", "gas_valve_close")

    async def async_press(self) -> None:
        body = {"request": "control", "number": "1", "onoff": "0"}
        await self.coordinator.client.async_publish(address="17", body=body)
        _LOGGER.info("Gas valve CLOSE command sent")


class CvnetHeatingAllOnButton(_BaseSystemButton):
    """Button to turn all heating zones ON."""

    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Heating All ON", "heating_all_on")

    async def async_press(self) -> None:
        body = {"request": "control_all", "onoff": "1"}
        await self.coordinator.client.async_publish(address="22", body=body)
        _LOGGER.info("Heating ALL ON command sent")
        await self.coordinator.async_request_refresh()


class CvnetHeatingAllOffButton(_BaseSystemButton):
    """Button to turn all heating zones OFF."""

    _attr_icon = "mdi:radiator-off"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "Heating All OFF", "heating_all_off")

    async def async_press(self) -> None:
        body = {"request": "control_all", "onoff": "0"}
        await self.coordinator.client.async_publish(address="22", body=body)
        _LOGGER.info("Heating ALL OFF command sent")
        await self.coordinator.async_request_refresh()
