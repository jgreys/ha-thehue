from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from ..const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL, CONF_VISITOR_ROWS, CONF_CAR_ROWS,
    DEFAULT_UPDATE_INTERVAL, DEFAULT_VISITOR_ROWS, DEFAULT_CAR_ROWS,
)
from ..api.client import Client, LoginError, ValidationError, ConnectionError

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
            
        # Check for duplicate entries
        await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_USERNAME]}")
        self._abort_if_unique_id_configured()
        
        session = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(session)
        
        try:
            await client.async_login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        except ValidationError:
            errors["base"] = "invalid_input"
        except LoginError:
            errors["base"] = "invalid_auth"
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            errors["base"] = "unknown"
        finally:
            await client.async_close()
            
        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )
            
        return self.async_create_entry(title="Hanshin The Hue", data=user_input)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options for CVNET."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options
        schema = vol.Schema({
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): vol.All(int, vol.Range(min=5, max=300)),
            vol.Optional(
                CONF_VISITOR_ROWS,
                default=current.get(CONF_VISITOR_ROWS, DEFAULT_VISITOR_ROWS),
            ): vol.All(int, vol.Range(min=1, max=50)),
            vol.Optional(
                CONF_CAR_ROWS,
                default=current.get(CONF_CAR_ROWS, DEFAULT_CAR_ROWS),
            ): vol.All(int, vol.Range(min=1, max=50)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
