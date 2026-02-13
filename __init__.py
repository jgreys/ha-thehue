
from __future__ import annotations

import logging
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN
from .core.coordinator import CvnetCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "camera", "select", "light", "sensor", "button", "binary_sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CVNET from a config entry."""
    coord = CvnetCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord

    # Kick a first refresh (fetches visitor list on success)
    try:
        await coord.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.debug("cvnet: first refresh failed (non-fatal): %s", e)

    # Forward platforms
    loaded = []
    for plat in PLATFORMS:
        try:
            await hass.config_entries.async_forward_entry_setups(entry, [plat])
            _LOGGER.info("cvnet: platform %s forwarded", plat)
            loaded.append(plat)
        except Exception as e:
            _LOGGER.warning("cvnet: platform %s forward failed: %s", plat, e)
    _LOGGER.info("cvnet: platforms forwarded = %s", loaded)
    
    # Listen for options updates
    entry.async_on_unload(
        entry.add_update_listener(_async_update_options)
    )

    # Register services
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


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up CVNET services."""
    
    async def force_refresh(call):
        """Force refresh of CVNET data."""
        entry_id = call.data.get("entry_id")
        if not entry_id:
            # Use first entry if none specified
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No CVNET entries found for force refresh")
                return
            entry_id = entries[0].entry_id
            
        coord = hass.data[DOMAIN].get(entry_id)
        if not coord:
            _LOGGER.error("CVNET coordinator not found for entry %s", entry_id)
            return
            
        _LOGGER.info("Forcing CVNET data refresh for entry %s", entry_id)
        await coord.async_request_refresh()
        
    async def clear_session(call):
        """Clear CVNET session."""
        entry_id = call.data.get("entry_id")
        if not entry_id:
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No CVNET entries found for clear session")
                return
            entry_id = entries[0].entry_id
            
        coord = hass.data[DOMAIN].get(entry_id)
        if not coord:
            _LOGGER.error("CVNET coordinator not found for entry %s", entry_id)
            return
            
        _LOGGER.info("Clearing CVNET session for entry %s", entry_id)
        # Clear session state
        if hasattr(coord.client, '_last_successful_request'):
            coord.client._last_successful_request = None
        await coord.async_request_refresh()
        
    async def session_info(call):
        """Get CVNET session info."""
        entry_id = call.data.get("entry_id") 
        if not entry_id:
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No CVNET entries found for session info")
                return
            entry_id = entries[0].entry_id
            
        coord = hass.data[DOMAIN].get(entry_id)
        if not coord:
            _LOGGER.error("CVNET coordinator not found for entry %s", entry_id)
            return
            
        info = coord.get_session_info()
        _LOGGER.info("CVNET session info for entry %s: %s", entry_id, info)
        
        # Create persistent notification with the info
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "CVNET Session Info",
                    "message": f"Session Info:\n{info}",
                    "notification_id": f"cvnet_session_{entry_id}"
                }
            )
        )

    # Register services
    hass.services.async_register(DOMAIN, "force_refresh", force_refresh)
    hass.services.async_register(DOMAIN, "clear_session", clear_session)
    hass.services.async_register(DOMAIN, "session_info", session_info)
