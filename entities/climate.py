
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from homeassistant.components.climate import ClimateEntity

_LOGGER = logging.getLogger(__name__)
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from ..core.coordinator import CvnetCoordinator

ROOMS = [
    {"name": "거실 난방", "number": "1", "off_special": True},
    {"name": "방1 난방", "number": "2"},
    {"name": "방2 난방", "number": "3"},
    {"name": "방3 난방", "number": "4"},
]

# Debounce settings to prevent race conditions with rapid button clicks
COMMAND_DEBOUNCE_SECONDS = 3.0  # Ignore coordinator updates for this long after a command
REFRESH_DELAY_SECONDS = 2.0  # Wait this long after last command before refreshing

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


class CVNETClimate(CoordinatorEntity, ClimateEntity):
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_min_temp = 5
    _attr_max_temp = 40
    _attr_precision = 1.0
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: CvnetCoordinator, room: dict) -> None:
        super().__init__(coordinator)
        self._name = room["name"]
        self._number = room["number"]
        self._off_special = room.get("off_special", False)
        self._attr_unique_id = f"cvnet_heat_{self._number}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_heating")}, name="Heating", manufacturer="CVNET")
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 20.0
        self._attr_current_temperature: Optional[float] = None
        # Debounce tracking to prevent race conditions with rapid commands
        self._last_command_time: float = 0.0
        self._pending_refresh_task: Optional[asyncio.Task] = None

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
                _LOGGER.debug("Setting HVAC mode %s for room %s: %s", hvac_mode, self._number, body)
                await publish(address="22", body=body)
                # Update local state immediately (optimistic) and track command time
                self._attr_hvac_mode = hvac_mode
                self._last_command_time = time.monotonic()
                self.async_write_ha_state()
                # Schedule debounced refresh
                self._schedule_debounced_refresh()
            except Exception as ex:
                _LOGGER.error("Failed to set HVAC mode for room %s: %s", self._number, ex)
        else:
            _LOGGER.warning("async_publish not available on coordinator.client")
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
                _LOGGER.debug("Setting temperature %s for room %s: %s", t, self._number, body)
                await publish(address="22", body=body)
                # Update local state immediately (optimistic) and track command time
                self._attr_target_temperature = float(t)
                self._last_command_time = time.monotonic()
                self.async_write_ha_state()
                # Schedule debounced refresh - cancel any pending refresh first
                self._schedule_debounced_refresh()
            except Exception as ex:
                _LOGGER.error("Failed to set temperature for room %s: %s", self._number, ex)
        else:
            _LOGGER.warning("async_publish not available on coordinator.client")
            self._attr_target_temperature = float(t)
            self.async_write_ha_state()

    def _schedule_debounced_refresh(self) -> None:
        """Schedule a coordinator refresh after debounce delay, canceling any pending refresh."""
        # Cancel any existing pending refresh
        if self._pending_refresh_task and not self._pending_refresh_task.done():
            self._pending_refresh_task.cancel()
        # Schedule new refresh after delay
        self._pending_refresh_task = asyncio.create_task(self._delayed_refresh())

    async def _delayed_refresh(self) -> None:
        """Wait for debounce period then request coordinator refresh."""
        try:
            await asyncio.sleep(REFRESH_DELAY_SECONDS)
            _LOGGER.debug("Debounced refresh triggered for room %s", self._number)
            await self.coordinator.async_request_refresh()
        except asyncio.CancelledError:
            _LOGGER.debug("Debounced refresh cancelled for room %s (new command received)", self._number)
        except Exception as ex:
            _LOGGER.warning("Debounced refresh failed for room %s: %s", self._number, ex)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        heaters = (self.coordinator.data or {}).get("heaters") or {}
        body = heaters.get("body") if isinstance(heaters, dict) else None
        if isinstance(body, dict):
            for item in body.get("contents", []):
                if str(item.get("number")) == self._number:
                    # Parse current_temp, handling both int and string values
                    ct = item.get("current_temp")
                    if ct is not None:
                        try:
                            self._attr_current_temperature = float(ct)
                        except (ValueError, TypeError):
                            pass
                    # Parse onoff - but respect debounce window to avoid race conditions
                    onoff = item.get("onoff")
                    server_hvac_mode = HVACMode.HEAT if str(onoff) == "1" else HVACMode.OFF
                    time_since_command = time.monotonic() - self._last_command_time
                    if time_since_command > COMMAND_DEBOUNCE_SECONDS:
                        # Safe to update from server - no recent commands
                        self._attr_hvac_mode = server_hvac_mode
                    elif server_hvac_mode == self._attr_hvac_mode:
                        # Server confirms our optimistic update
                        _LOGGER.debug("Server confirmed HVAC mode %s for room %s", server_hvac_mode, self._number)
                    else:
                        # Within debounce window and server disagrees - keep optimistic value
                        _LOGGER.warning(
                            "Ignoring stale server HVAC mode %s for room %s (local: %s, %.1fs since command)",
                            server_hvac_mode, self._number, self._attr_hvac_mode, time_since_command
                        )
                    # Parse setting_temp - reuse time_since_command from above
                    st = item.get("setting_temp")
                    if st is not None:
                        server_temp = float(_clamp_int_temp(st))
                        if time_since_command > COMMAND_DEBOUNCE_SECONDS:
                            # Safe to update from server - no recent commands
                            self._attr_target_temperature = server_temp
                        elif server_temp == self._attr_target_temperature:
                            # Server confirms our optimistic update
                            _LOGGER.debug("Server confirmed temp %s for room %s", server_temp, self._number)
                        else:
                            # Within debounce window and server disagrees - keep optimistic value
                            _LOGGER.warning(
                                "Ignoring stale server temp %s for room %s (local: %s, %.1fs since command)",
                                server_temp, self._number, self._attr_target_temperature, time_since_command
                            )
                    break
        # Call parent to write state
        super()._handle_coordinator_update()
