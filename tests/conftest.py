"""Shared test fixtures for ha-thehue.

Since this is a Home Assistant custom component, HA is not installed in the
test environment. We mock the HA modules so that our project code can be imported
as if it were custom_components.cvnet.
"""
from __future__ import annotations

import sys
import os
import types
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Stub out homeassistant modules BEFORE importing project code
# ---------------------------------------------------------------------------

def _make_module(name, parent=None, attrs=None):
    mod = types.ModuleType(name)
    mod.__path__ = []
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    if parent:
        setattr(parent, name.rsplit(".", 1)[-1], mod)
    return mod

# Sentinel classes used by HA
class _FakeEntity:
    pass

class _FakeCoordinatorEntity:
    def __init__(self, *a, **kw):
        self.coordinator = a[0] if a else None

class _FakeDataUpdateCoordinator:
    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self._logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None
    async def async_config_entry_first_refresh(self): pass
    async def async_request_refresh(self): pass
    def async_set_updated_data(self, data): self.data = data
    def __class_getitem__(cls, item): return cls

class _FakeUpdateFailed(Exception):
    pass

class _FakeConfigFlow:
    def __init_subclass__(cls, **kw): pass

class _FakeOptionsFlow:
    pass

class _FakeFlowResult(dict):
    pass

class _FakeSensorEntity(_FakeEntity):
    pass

class _FakeSensorDeviceClass:
    ENERGY = "energy"
    WATER = "water"
    GAS = "gas"
    TEMPERATURE = "temperature"

class _FakeSensorStateClass:
    TOTAL_INCREASING = "total_increasing"
    MEASUREMENT = "measurement"

class _FakeDeviceInfo:
    def __init__(self, **kw): pass

class _FakeUnitOfEnergy:
    KILO_WATT_HOUR = "kWh"

class _FakeUnitOfVolume:
    CUBIC_METERS = "m³"

class _FakeUnitOfTemperature:
    CELSIUS = "°C"

# Build the HA module tree
ha = _make_module("homeassistant")
ha_core = _make_module("homeassistant.core", ha, {"HomeAssistant": MagicMock, "callback": lambda f: f})
ha_const = _make_module("homeassistant.const", ha, {
    "CONF_USERNAME": "username",
    "CONF_PASSWORD": "password",
    "UnitOfEnergy": _FakeUnitOfEnergy,
    "UnitOfVolume": _FakeUnitOfVolume,
    "UnitOfTemperature": _FakeUnitOfTemperature,
})
ha_config_entries = _make_module("homeassistant.config_entries", ha, {
    "ConfigEntry": MagicMock,
    "ConfigFlow": _FakeConfigFlow,
    "OptionsFlow": _FakeOptionsFlow,
})
ha_helpers = _make_module("homeassistant.helpers", ha)
ha_helpers_aiohttp = _make_module("homeassistant.helpers.aiohttp_client", ha_helpers, {
    "async_get_clientsession": MagicMock(),
})
ha_helpers_entity = _make_module("homeassistant.helpers.entity", ha_helpers, {
    "DeviceInfo": _FakeDeviceInfo,
})
ha_helpers_entity_platform = _make_module("homeassistant.helpers.entity_platform", ha_helpers, {
    "AddEntitiesCallback": MagicMock,
})
ha_helpers_update_coordinator = _make_module("homeassistant.helpers.update_coordinator", ha_helpers, {
    "DataUpdateCoordinator": _FakeDataUpdateCoordinator,
    "CoordinatorEntity": _FakeCoordinatorEntity,
    "UpdateFailed": _FakeUpdateFailed,
})
ha_data_entry_flow = _make_module("homeassistant.data_entry_flow", ha, {
    "FlowResult": _FakeFlowResult,
})
ha_components = _make_module("homeassistant.components", ha)
ha_components_sensor = _make_module("homeassistant.components.sensor", ha_components, {
    "SensorEntity": _FakeSensorEntity,
    "SensorDeviceClass": _FakeSensorDeviceClass,
    "SensorStateClass": _FakeSensorStateClass,
})
ha_components_light = _make_module("homeassistant.components.light", ha_components, {
    "LightEntity": _FakeEntity,
    "ColorMode": MagicMock(ONOFF="onoff"),
})
ha_components_camera = _make_module("homeassistant.components.camera", ha_components, {
    "Camera": _FakeEntity,
})
ha_components_climate = _make_module("homeassistant.components.climate", ha_components, {
    "ClimateEntity": _FakeEntity,
    "HVACMode": MagicMock(OFF="off", HEAT="heat"),
    "ClimateEntityFeature": MagicMock(),
})
ha_components_select = _make_module("homeassistant.components.select", ha_components, {
    "SelectEntity": _FakeEntity,
})
ha_components_button = _make_module("homeassistant.components.button", ha_components, {
    "ButtonEntity": _FakeEntity,
})
ha_components_switch = _make_module("homeassistant.components.switch", ha_components, {
    "SwitchEntity": _FakeEntity,
})
ha_components_binary_sensor = _make_module("homeassistant.components.binary_sensor", ha_components, {
    "BinarySensorEntity": _FakeEntity,
    "BinarySensorDeviceClass": MagicMock(CONNECTIVITY="connectivity"),
})

# voluptuous stub
if "voluptuous" not in sys.modules:
    vol = _make_module("voluptuous")
    vol.Schema = lambda *a, **kw: MagicMock()
    vol.Required = lambda *a, **kw: a[0]
    vol.Optional = lambda *a, **kw: a[0] if a else kw.get("default")
    vol.All = lambda *a: a[-1]
    vol.Range = lambda **kw: kw

# ---------------------------------------------------------------------------
# Set up the project as a proper package so relative imports work.
# The project dir "ha-thehue" acts as a HA custom component that uses
# relative imports like `from ..const import DOMAIN`.
# We register it as a package so `from <pkg>.api.client import Client` works.
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_NAME = "cvnet"  # canonical name for the integration

# Register the project root as a package named "cvnet"
import importlib.util

spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    os.path.join(PROJECT_ROOT, "__init__.py"),
    submodule_search_locations=[PROJECT_ROOT],
)
pkg = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE_NAME] = pkg
pkg.__path__ = [PROJECT_ROOT]
pkg.__package__ = PACKAGE_NAME

# Register sub-packages
for sub in ("api", "core", "entities"):
    sub_dir = os.path.join(PROJECT_ROOT, sub)
    sub_full = f"{PACKAGE_NAME}.{sub}"
    sub_spec = importlib.util.spec_from_file_location(
        sub_full,
        os.path.join(sub_dir, "__init__.py"),
        submodule_search_locations=[sub_dir],
    )
    sub_mod = importlib.util.module_from_spec(sub_spec)
    sub_mod.__package__ = sub_full
    sys.modules[sub_full] = sub_mod
    setattr(pkg, sub, sub_mod)

# Now import actual modules
for mod_name, rel_path in [
    ("cvnet.const", "const.py"),
    ("cvnet.api.client", "api/client.py"),
    ("cvnet.core.coordinator", "core/coordinator.py"),
    ("cvnet.core.config_flow", "core/config_flow.py"),
    ("cvnet.entities.sensor", "entities/sensor.py"),
]:
    full_path = os.path.join(PROJECT_ROOT, rel_path)
    mod_spec = importlib.util.spec_from_file_location(mod_name, full_path)
    mod = importlib.util.module_from_spec(mod_spec)
    mod.__package__ = mod_name.rsplit(".", 1)[0]
    sys.modules[mod_name] = mod
    mod_spec.loader.exec_module(mod)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
import aiohttp
from cvnet.api.client import Client


def _make_async_cm(return_value):
    """Create an async context manager mock."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession with async context managers."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.close = AsyncMock()
    return session


@pytest.fixture
def client(mock_session):
    """Create a Client with a mock session."""
    return Client(session=mock_session)


@pytest.fixture
def mock_hass():
    """Minimal mock HomeAssistant object."""
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_entry():
    """Mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"username": "testuser", "password": "testpass"}
    entry.options = {}
    return entry
