from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfEnergy, UnitOfVolume, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN, MAX_VISITOR_ATTRIBUTES
from ..core.coordinator import CvnetCoordinator

ROOMS = [
    {"name": "거실", "number": "1"},
    {"name": "방1", "number": "2"},
    {"name": "방2", "number": "3"},
    {"name": "방3", "number": "4"},
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: CvnetCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ElecSensor(coord), WaterSensor(coord), GasSensor(coord)]
    entities.extend([RoomTempSensor(coord, r) for r in ROOMS])
    visitors_sensor = CvnetVisitorsSensor(coord)
    visitors_sensor.set_hass(hass)
    entities.append(visitors_sensor)
    car_entries_sensor = CvnetCarEntriesSensor(coord, entry)
    car_entries_sensor.set_hass(hass)
    entities.append(car_entries_sensor)
    async_add_entities(entities, update_before_add=False)

class BaseEntity(SensorEntity):
    def __init__(self, coordinator: CvnetCoordinator):
        self.coordinator = coordinator

class BaseTele(BaseEntity):
    def __init__(self, coordinator: CvnetCoordinator, name: str, key: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"cvnet_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_telemeter")}, name="Telemeter", manufacturer="CVNET")

    @property
    def native_value(self):
        tele = (self.coordinator.data or {}).get("telemeter") or {}
        val = tele.get(self._key)
        try:
            return float(val)
        except Exception:
            return None

class ElecSensor(BaseTele):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True
    _attr_translation_key = "electricity"
    def __init__(self, coord): super().__init__(coord, "Electricity (kWh)", "electric")

class WaterSensor(BaseTele):
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_has_entity_name = True
    _attr_translation_key = "water"
    def __init__(self, coord): super().__init__(coord, "Water (m³)", "water")

class GasSensor(BaseTele):
    _attr_device_class = SensorDeviceClass.GAS
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_has_entity_name = True
    _attr_translation_key = "gas"
    def __init__(self, coord): super().__init__(coord, "Gas (m³)", "gas")

class RoomTempSensor(BaseEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: CvnetCoordinator, room: dict):
        super().__init__(coordinator)
        self._number = str(room["number"])
        self._attr_name = f"{room['name']} 현재온도"
        self._attr_unique_id = f"cvnet_room_{self._number}_current_temp"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "cvnet_heating")}, name="Heating", manufacturer="CVNET")

    @property
    def native_value(self):
        heaters = (self.coordinator.data or {}).get("heaters") or {}
        body = heaters.get("body") if isinstance(heaters, dict) else None
        if isinstance(body, dict):
            for item in body.get("contents", []):
                if str(item.get("number")) == self._number:
                    return item.get("current_temp")
        return None



class CvnetVisitorsSensor(BaseEntity):
    """Unified sensor for visitor list, selection, and image."""
    _attr_icon = "mdi:account-group"

    def __init__(self, coordinator: CvnetCoordinator):
        super().__init__(coordinator)
        self._attr_name = "Visitors"
        self._attr_unique_id = "cvnet_visitors"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "cvnet_visitors")},
            name="Visitors",
            manufacturer="CVNET",
        )
        self._file_name: str | None = None
        self._image_data_url: str | None = None
        self._visitor_list: list = []
        self._last_notified_date: str | None = None
        self._hass: HomeAssistant | None = None

    def set_hass(self, hass: HomeAssistant):
        self._hass = hass

    @property
    def native_value(self):
        # State: currently selected visitor file_name
        return self._file_name

    @property
    def extra_state_attributes(self):
        # Limit attribute size to avoid Recorder 16KB cap.
        simplified = []
        for v in self._visitor_list[:MAX_VISITOR_ATTRIBUTES]:
            simplified.append({
                "file_name": v.get("file_name"),
                "date_time": v.get("date_time"),
                "title": v.get("title"),
            })
        attrs = {
            "file_name": self._file_name,
            # Indicate image availability instead of embedding huge base64
            "has_image": bool(self._image_data_url),
            "visitor_count": len(self._visitor_list),
            "visitors": simplified,
        }
        return attrs

    async def async_update(self):
        # Get latest visitor list and selected file_name
        items = (self.coordinator.data.get("vis") or {}).get("contents") if self.coordinator.data else None
        self._visitor_list = items or []
        file_name = self.coordinator.get_visitor_selected()
        if not file_name and self._visitor_list:
            file_name = self._visitor_list[0].get("file_name")
        self._file_name = file_name
        if not file_name:
            self._image_data_url = None
            return
        # Don't fetch/store full base64 here (keeps state small). Camera entity retrieves image on demand.
        self._image_data_url = None

        # Notification logic
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        new_visitor = None
        for v in self._visitor_list:
            dt = v.get("date_time", "")
            if dt.startswith(today):
                if self._last_notified_date != dt:
                    new_visitor = v
                    break
        if new_visitor and self._hass:
            # Send notification using configured notify service
            notify_service = None
            if hasattr(self._hass, 'config_entries'):
                # Try to get from config entry options
                entries = self._hass.config_entries.async_entries(DOMAIN)
                if entries:
                    entry = entries[0]
                    notify_service = entry.options.get("notify_service")
            if not notify_service:
                notify_service = "persistent_notification.create"  # fallback to persistent notification
            title = new_visitor.get("title", "New Visitor")
            dt = new_visitor.get("date_time", "")
            await self._hass.services.async_call(
                "notify",
                notify_service,
                {
                    "message": f"New visitor: {title} at {dt}",
                    "title": "CVNET Visitor Alert"
                },
                blocking=True
            )
            self._last_notified_date = dt


class CvnetCarEntriesSensor(BaseEntity):
    """Sensor that exposes the latest car entrance list with pagination info."""

    _attr_icon = "mdi:car-info"

    def __init__(self, coordinator: CvnetCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_name = "Car Entries"
        self._attr_unique_id = f"{entry.entry_id}_car_entries"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_car")},
            name="Car Entrance",
            manufacturer="CVNET",
        )
        self._last_notified_date: str | None = None
        self._hass: HomeAssistant | None = None

    def set_hass(self, hass: HomeAssistant):
        self._hass = hass

    @property
    def native_value(self):
        car = self.coordinator.car_state()
        return len(car.get("contents", []))

    @property
    def extra_state_attributes(self):
        car = self.coordinator.car_state()
        items = car.get("contents") or []
        simplified = [{"title": it.get("title"), "date_time": it.get("date_time"), "inout": it.get("inout")} for it in items]
        return {
            "entries": simplified,
            "page_no": car.get("page_no"),
            "rows": car.get("rows"),
            "exist_next": car.get("exist_next"),
        }

    async def async_update(self):
        car = self.coordinator.car_state()
        # Notification logic
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        new_entry = None
        for v in car.get("contents", []):
            dt = v.get("date_time", "")
            if dt.startswith(today):
                if self._last_notified_date != dt:
                    new_entry = v
                    break
        if new_entry and self._hass:
            # Send notification using configured notify service
            notify_service = None
            if hasattr(self._hass, 'config_entries'):
                entries = self._hass.config_entries.async_entries(DOMAIN)
                if entries:
                    entry = entries[0]
                    notify_service = entry.options.get("notify_service")
            if not notify_service:
                notify_service = "persistent_notification.create"  # fallback to persistent notification
            title = new_entry.get("title", "New Car Entry")
            dt = new_entry.get("date_time", "")
            await self._hass.services.async_call(
                "notify",
                notify_service,
                {
                    "message": f"New car entry: {title} at {dt}",
                    "title": "CVNET Car Entry Alert"
                },
                blocking=True
            )
            self._last_notified_date = dt
