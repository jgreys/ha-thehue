
from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

ROOMS = [
    {"name": "거실 난방", "number": "1", "off_special": True},
    {"name": "방1 난방", "number": "2"},
    {"name": "방2 난방", "number": "3"},
    {"name": "방3 난방", "number": "4"},
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [CVNETClimate(coordinator, room) for room in ROOMS]
    async_add_entities(entities)


def _clamp_int_temp(val: Any, minimum: int = 5, maximum: int = 40) -> int:
    try:
        ival = int(round(float(val)))
    except Exception:
        ival = 20
    return max(minimum, min(maximum, ival))


class CVNETClimate(ClimateEntity):
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_min_temp = 5
    _attr_max_temp = 40
    _attr_precision = 0.5

    def __init__(self, coordinator: CvnetCoordinator, room: dict) -> None:
        self.coordinator = coordinator
        self._name = room["name"]
        self._number = room["number"]
        self._off_special = room.get("off_special", False)
        self._attr_unique_id = f"cvnet_heat_{self._number}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_heating")}, name="Heating", manufacturer="CVNET")
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 20.0
        self._attr_current_temperature: Optional[float] = None

    @property
    def name(self) -> str:
        return self._name

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # Build request body as best as we can; guard if backend call is unavailable
        t = _clamp_int_temp(self._attr_target_temperature)
        onoff = "0" if hvac_mode == HVACMode.OFF else "1"
        body = {
            "request": "control",
            "number": self._number,
            "onoff": onoff,
            "temp": str(t),
        }
        publish = getattr(self.coordinator.client, "async_publish", None)
        if callable(publish):
            try:
                await publish(address="22", body=body)
            except Exception:  # keep UI responsive even if backend refuses
                pass
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        t = _clamp_int_temp(temp)
        body = {
            "request": "control",
            "number": self._number,
            "onoff": "1" if self._attr_hvac_mode != HVACMode.OFF else "0",
            "temp": str(t),
        }
        publish = getattr(self.coordinator.client, "async_publish", None)
        if callable(publish):
            try:
                await publish(address="22", body=body)
            except Exception:
                pass
        self._attr_target_temperature = float(t)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        heaters = (self.coordinator.data or {}).get("heaters") or {}
        body = heaters.get("body") if isinstance(heaters, dict) else None
        if isinstance(body, dict):
            for item in body.get("contents", []):
                if str(item.get("number")) == self._number:
                    self._attr_current_temperature = item.get("current_temp")
                    onoff = item.get("onoff")
                    self._attr_hvac_mode = HVACMode.HEAT if onoff == 1 else HVACMode.OFF
                    st = item.get("setting_temp")
                    if st is not None:
                        self._attr_target_temperature = float(_clamp_int_temp(st))
                    break
