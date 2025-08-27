from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from ..const import DOMAIN
from ..api.client import Client, LoginError, ValidationError, ConnectionError

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_options(self, user_input=None):
        options_schema = vol.Schema({
            vol.Required("notify_service", default=(self.options.get("notify_service") if self.options else "")): str
        })
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)
        return self.async_show_form(step_id="options", data_schema=options_schema)
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
