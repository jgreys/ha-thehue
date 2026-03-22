
from __future__ import annotations

import logging
from typing import Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.persistent_notification import async_create as pn_async_create

from .const import DOMAIN
from .core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "camera", "select", "light", "sensor", "button", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CVNET from a config entry."""
    coord = CvnetCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord

    try:
        await coord.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.debug("cvnet: first refresh failed (non-fatal): %s", e)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        entry.add_update_listener(_async_update_options)
    )

    await _async_setup_services(hass)

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coord: CvnetCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coord:
        coord.apply_options(dict(entry.options))
        await coord.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coord: CvnetCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coord:
        try:
            await coord.async_close()
        except Exception:
            pass
    return unload_ok


def _resolve_coordinator(hass: HomeAssistant, call: ServiceCall) -> Optional[CvnetCoordinator]:
    """Resolve coordinator from a service call, defaulting to the first entry."""
    entry_id = call.data.get("entry_id")
    if not entry_id:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("No CVNET entries found")
            return None
        entry_id = entries[0].entry_id

    coord = hass.data[DOMAIN].get(entry_id)
    if not coord:
        _LOGGER.error("CVNET coordinator not found for entry %s", entry_id)
    return coord


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up CVNET services."""

    async def force_refresh(call: ServiceCall):
        coord = _resolve_coordinator(hass, call)
        if not coord:
            return
        _LOGGER.info("Forcing CVNET data refresh")
        await coord.async_request_refresh()

    async def clear_session(call: ServiceCall):
        coord = _resolve_coordinator(hass, call)
        if not coord:
            return
        _LOGGER.info("Clearing CVNET session")
        coord.client.invalidate_session()
        await coord.async_request_refresh()

    async def session_info(call: ServiceCall):
        coord = _resolve_coordinator(hass, call)
        if not coord:
            return
        info = coord.get_session_info()
        _LOGGER.info("CVNET session info: %s", info)
        pn_async_create(
            hass,
            f"Session Info:\n{info}",
            title="CVNET Session Info",
            notification_id="cvnet_session_info",
        )

    hass.services.async_register(DOMAIN, "force_refresh", force_refresh)
    hass.services.async_register(DOMAIN, "clear_session", clear_session)
    hass.services.async_register(DOMAIN, "session_info", session_info)
