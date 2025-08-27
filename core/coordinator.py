from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DEFAULT_VISITOR_ROWS, DEFAULT_CAR_ROWS
from ..api.client import Client, LoginError, ApiError, ConnectionError

_LOGGER = logging.getLogger(__name__)

class CvnetCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass, 
            _LOGGER, 
            name="cvnet", 
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
        )
        self.hass = hass
        self.entry = entry
        self.client = Client(async_get_clientsession(hass))
        self._visitor_list = []
        self._selected = None
        # Visitor pagination
        self._visitor_rows = DEFAULT_VISITOR_ROWS
        self._visitor_page_no = 1
        self._visitor_exist_next = False
        # Car entries state
        self._car_rows = DEFAULT_CAR_ROWS
        self._car_page_no = 1
        self._car_exist_next = False
        self._car_contents = []

    async def async_prime_visitors(self) -> None:
        try:
            data = await self.client.async_visitor_list(page_no=self._visitor_page_no, rows=self._visitor_rows)
            self._visitor_list = data
            self._selected = (self._visitor_list[0]["file_name"] if self._visitor_list else None)
            _LOGGER.debug("Primed visitors: %d items, selected=%s", len(self._visitor_list), self._selected)
        except Exception as err:
            _LOGGER.debug("visitor_list failed during prime: %s", err)

    async def _async_update_data(self) -> dict:
        """Fetch data from CVNET API.
        
        Returns:
            Dictionary containing visitor and car entry data
            
        Raises:
            UpdateFailed: If critical data update fails
        """
        # Ensure credentials are available
        username = self.entry.data.get(CONF_USERNAME)
        password = self.entry.data.get(CONF_PASSWORD)
        if not username or not password:
            raise UpdateFailed("Missing credentials in config entry")

        # Ensure client has credentials for re-authentication
        if not getattr(self.client, "_creds", None):
            try:
                await self.client.async_login(username, password)
                _LOGGER.debug("Initial login successful")
            except LoginError as e:
                _LOGGER.warning("cvnet initial login failed during update: %s", e)
                raise UpdateFailed(f"Initial login failed: {e}")
            except (ApiError, ConnectionError) as e:
                _LOGGER.warning("cvnet initial connection failed during update: %s", e)
                raise UpdateFailed(f"Initial connection failed: {e}")

        visitor_success = False
        car_success = False

        # Refresh visitors periodically
        try:
            data = await self.client.async_visitor_list(page_no=self._visitor_page_no, rows=self._visitor_rows)
            self._visitor_list = data or []
            if self._visitor_list and (self._selected is None or self._selected not in [i.get("file_name") for i in self._visitor_list]):
                self._selected = self._visitor_list[0].get("file_name")
            # Visitor pagination: check if next page exists
            self._visitor_exist_next = len(self._visitor_list) >= self._visitor_rows
            visitor_success = True
            _LOGGER.debug("Visitor list updated successfully: %d items", len(self._visitor_list))
        except (ApiError, ConnectionError) as err:
            _LOGGER.warning("visitor_list failed during update: %s", err)
            # Keep existing data but mark as failed
        except Exception as err:
            _LOGGER.error("Unexpected error during visitor_list update: %s", err)

        # Refresh car entries with current pagination
        try:
            car = await self.client.async_entrancecar_list(page_no=self._car_page_no, rows=self._car_rows)
            self._car_contents = car.get("contents", [])
            # Normalize numbers
            try:
                self._car_page_no = int(str(car.get("page_no") or self._car_page_no).lstrip("0") or "1")
            except (ValueError, TypeError):
                self._car_page_no = max(1, self._car_page_no)
            try:
                self._car_rows = int(str(car.get("rows") or self._car_rows))
            except (ValueError, TypeError):
                pass
            self._car_exist_next = bool(car.get("exist_next", False))
            car_success = True
            _LOGGER.debug("Car entries updated successfully: %d items", len(self._car_contents))
        except (ApiError, ConnectionError) as err:
            _LOGGER.warning("entrancecar_list failed during update: %s", err)
            # Keep existing data but mark as failed
        except Exception as err:
            _LOGGER.error("Unexpected error during entrancecar_list update: %s", err)

        # Only fail the entire update if both critical data sources fail
        if not visitor_success and not car_success:
            _LOGGER.error("Both visitor and car data updates failed - this may indicate session expiration or connectivity issues")
            # Force re-authentication on next update by clearing session state
            if hasattr(self.client, '_last_successful_request'):
                self.client._last_successful_request = None  # Force session expiration check
            raise UpdateFailed("All data sources failed - session may be expired")

        return {
            "ok": True,
            "vis": {
                "contents": self._visitor_list,
                "page_no": self._visitor_page_no,
                "rows": self._visitor_rows,
                "exist_next": self._visitor_exist_next,
            },
            "selected": self._selected,
            "car": {
                "contents": self._car_contents,
                "page_no": self._car_page_no,
                "rows": self._car_rows,
                "exist_next": self._car_exist_next,
            },
        }

    # Visitor pagination controls
    async def async_visitor_set_rows(self, rows: int) -> None:
        if rows <= 0:
            rows = 5
        self._visitor_rows = rows
        self._visitor_page_no = 1
        await self.async_request_refresh()

    async def async_visitor_next_page(self) -> None:
        if self._visitor_exist_next:
            self._visitor_page_no += 1
            await self.async_request_refresh()

    async def async_visitor_prev_page(self) -> None:
        if self._visitor_page_no > 1:
            self._visitor_page_no -= 1
            await self.async_request_refresh()

    def visitor_state(self) -> dict:
        return {
            "contents": list(self._visitor_list),
            "page_no": self._visitor_page_no,
            "rows": self._visitor_rows,
            "exist_next": self._visitor_exist_next,
        }

    # Exposed helpers used by entities
    def visitor_options(self) -> List[str]:
        return [item.get("file_name") for item in self._visitor_list]

    def get_visitor_selected(self) -> Optional[str]:
        if self._selected:
            return self._selected
        return self._visitor_list[0]["file_name"] if self._visitor_list else None

    def set_visitor_selected(self, file_name: str) -> None:
        self._selected = file_name
        self.async_set_updated_data({"selected": file_name})

    # ---------- Car entries controls ----------
    async def async_car_set_rows(self, rows: int) -> None:
        if rows <= 0:
            rows = 5
        self._car_rows = rows
        self._car_page_no = 1
        await self.async_request_refresh()

    async def async_car_next_page(self) -> None:
        # Only advance if server says there's a next page, but allow manual advance if unknown
        if self._car_exist_next:
            self._car_page_no += 1
            await self.async_request_refresh()

    async def async_car_prev_page(self) -> None:
        if self._car_page_no > 1:
            self._car_page_no -= 1
            await self.async_request_refresh()

    # Read helpers
    def car_state(self) -> dict:
        return {
            "contents": list(self._car_contents),
            "page_no": self._car_page_no,
            "rows": self._car_rows,
            "exist_next": self._car_exist_next,
        }

    def get_session_info(self) -> dict:
        """Get diagnostic information about the current session."""
        info = {
            "has_credentials": bool(getattr(self.client, "_creds", None)),
            "username": getattr(self.client, "_username", None),
            "last_successful_request": getattr(self.client, "_last_successful_request", None),
            "session_expired": getattr(self.client, "_is_session_expired", lambda: None)() if hasattr(self.client, "_is_session_expired") else None,
        }
        if info["last_successful_request"]:
            import time
            info["last_successful_ago_hours"] = (time.time() - info["last_successful_request"]) / 3600
        return info

    async def async_close(self) -> None:
        try:
            await self.client.async_close()
        except Exception:
            pass
