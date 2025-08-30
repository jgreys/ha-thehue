from __future__ import annotations
import json
import base64
import logging
import asyncio
from typing import Any, Dict, Optional
import aiohttp
from aiohttp import ClientError, ServerDisconnectedError, WSMsgType
import secrets
import random

from ..const import (
    BASE,
    DEFAULT_TIMEOUT_S,
    DEFAULT_WS_BASE,
    VISITOR_LIST_PATH,
    VISITOR_CONTENT_PATH,
    VISITOR_REFERER,
    ENTRANCECAR_LIST_PATH,
    ENTRANCECAR_REFERER,
    SESSION_TIMEOUT_HOURS,
    ajax_headers,
    common_headers,
    ws_headers,
    UA,
)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT_S)

_LOGGER = logging.getLogger(__name__)

class LoginError(Exception):
    """Raised when authentication fails."""
    pass

class ApiError(Exception):
    """Raised when API calls fail."""
    pass

class ConnectionError(Exception):
    """Raised when connection issues occur."""
    pass

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

class Client:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        # HTTP session and ownership
        self._session = session or aiohttp.ClientSession()
        self._owns_session = session is None

        # State
        self._ws = None  # type: Optional[aiohttp.ClientWebSocketResponse]
        self._ws_base = None  # type: Optional[str]
        self._remote_addr = None  # type: Optional[str]
        self._dev_id = None  # type: Optional[str]
        self._username = None  # type: Optional[str]
        self._registered = set()  # type: set
        self._sockjs_server = None  # type: Optional[str]
        self._sockjs_session = None  # type: Optional[str]
        self._creds = None  # type: Optional[tuple]
        self._last_successful_request = None  # type: Optional[float]

    # ---------- Auth / Priming ----------
    async def async_login(self, username: str, password: str) -> None:
        """Authenticate with the CVNET service.
        
        Args:
            username: User login name
            password: User password
            
        Raises:
            ValidationError: If credentials are invalid format
            LoginError: If authentication fails
        """
        if not username or not isinstance(username, str):
            raise ValidationError("Username must be a non-empty string")
        if not password or not isinstance(password, str):
            raise ValidationError("Password must be a non-empty string")
            
        self._username = username.strip()
        self._creds = (self._username, password)
        form = {"id": self._username, "password": password, "deviceId": "0", "tokenId": "0"}
        url = f"{BASE}/cvnet/web/login.do"
        _LOGGER.debug("Login POST -> %s as %s", url, self._username)
        async with self._session.post(url, data=form, headers=ajax_headers(), allow_redirects=False, timeout=DEFAULT_TIMEOUT) as resp:
            txt = await resp.text()
            if resp.status != 200:
                raise LoginError(f"login HTTP {resp.status}: {txt[:160]}")
            try:
                data = json.loads(txt)
                if isinstance(data, dict):
                    res = str(data.get("result", "1")).lower()
                    if res in ("0", "fail", "false"):
                        msg = data.get("message") or "Invalid credentials"
                        raise LoginError(msg)
            except json.JSONDecodeError:
                pass
        await self._prime_cookies()
        verify = f"{BASE}/cvnet/web/telemetering.view"
        async with self._session.get(verify, headers=common_headers(), timeout=DEFAULT_TIMEOUT) as r2:
            if r2.status == 401:
                raise LoginError("Login appeared to succeed but telemetering.view returned 401.")
        try:
            await self.async_device_info("0x12")
        except Exception as e:
            _LOGGER.debug("device_info after login failed (ignored): %s", e)
        
        # Mark successful login
        import time
        self._last_successful_request = time.time()

    async def _prime_cookies(self) -> None:
        try:
            async with self._session.get(f"{BASE}/cvnet/web/", headers=common_headers(), timeout=DEFAULT_TIMEOUT) as r0:
                _LOGGER.debug("Prime cookies GET /cvnet/web/ -> %s", r0.status)
            async with self._session.get(f"{BASE}/", headers=common_headers(), timeout=DEFAULT_TIMEOUT) as r1:
                _LOGGER.debug("Prime cookies GET / -> %s", r1.status)
            async with self._session.get(f"{BASE}/cvnet/web/telemetering.view", headers=common_headers(), timeout=DEFAULT_TIMEOUT) as r2:
                _LOGGER.debug("Prime cookies GET /telemetering.view -> %s", r2.status)
        except Exception as e:
            _LOGGER.debug("Prime cookies failed: %s", e)

    def _is_session_expired(self) -> bool:
        """Check if session might be expired based on time since last successful request."""
        if not self._last_successful_request:
            return True
        
        import time
        # Consider session expired after configured hours of no successful requests
        SESSION_TIMEOUT = SESSION_TIMEOUT_HOURS * 60 * 60  # Convert hours to seconds
        return (time.time() - self._last_successful_request) > SESSION_TIMEOUT

    async def _ensure_authenticated(self) -> None:
        """Ensure we have valid authentication, re-login if needed."""
        if not self._creds:
            raise LoginError("No credentials available for re-authentication")
            
        # If session appears expired or we have no recent successful requests, try to re-login
        if self._is_session_expired():
            _LOGGER.debug("Session appears expired, attempting re-authentication")
            await self.async_login(*self._creds)

    def _mark_successful_request(self) -> None:
        """Mark that we just had a successful request."""
        import time
        self._last_successful_request = time.time()

    # ---------- Basic REST endpoints ----------
    async def async_device_info(self, type_hex: str = "0x12") -> Dict[str, Any]:
        _LOGGER.debug("POST device_info.do type=%s", type_hex)
        async with self._session.post(
            f"{BASE}/cvnet/web/device_info.do",
            headers=ajax_headers(),
            data={"type": type_hex},
            timeout=DEFAULT_TIMEOUT,
        ) as resp:
            txt = await resp.text()
            if resp.status != 200:
                raise ApiError(f"device_info.do HTTP {resp.status}: {txt[:160]}")
            data = json.loads(txt)
            wsaddr = data.get("websock_address")
            if wsaddr:
                if wsaddr.startswith("http://"):
                    wsaddr = "ws" + wsaddr[4:]
                if wsaddr.startswith("https://"):
                    wsaddr = "wss://" + wsaddr[8:]
                self._ws_base = wsaddr
            self._remote_addr = data.get("tcp_remote_addr") or self._remote_addr
            self._dev_id = data.get("id") or self._dev_id
            return data

    async def async_visitor_list(self, page_no: int = 1, rows: int = 14) -> list[dict]:
        """Fetch visitor list with pagination.
        
        Args:
            page_no: Page number to fetch
            rows: Number of rows per page
            
        Returns:
            List of visitor dictionaries
            
        Raises:
            ApiError: If API call fails
        """
        # Proactively check session health
        await self._ensure_authenticated()
        
        headers = dict(ajax_headers())
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = f"{BASE}{VISITOR_REFERER}"
        payload = {"pageNo": str(page_no), "rows": str(rows)}
        url = f"{BASE}{VISITOR_LIST_PATH}"
        await self._prime_visitor()
        _LOGGER.debug("visitor_list POST %s body=%s", url, payload)
        
        async with self._session.post(url, headers=headers, data=payload, timeout=DEFAULT_TIMEOUT) as resp:
            if resp.status == 401:
                _LOGGER.debug("Got 401, attempting re-authentication")
                if await self._maybe_reauth():
                    return await self.async_visitor_list(page_no=page_no, rows=rows)
                else:
                    raise ApiError("Authentication failed after retry")
            txt = await resp.text()
            if resp.status != 200:
                raise ApiError(f"visitor_list HTTP {resp.status}: {txt[:160]}")
            try:
                data = json.loads(txt)
                self._mark_successful_request()  # Mark successful request
            except Exception as ex:
                _LOGGER.error("visitor_list invalid JSON: %s", ex)
                return []
            return data.get("contents", []) if isinstance(data, dict) else []

    async def async_entrancecar_list(self, page_no: int = 1, rows: int = 14) -> dict:
        """Fetch car entrance list. Returns a dict with keys: contents, exist_next, page_no, rows, etc.

        Example item in contents: {"inout":"0","date_time":"2025-08-09 17:55","title":"14러1706"}
        """
        # Proactively check session health
        await self._ensure_authenticated()
        
        headers = dict(ajax_headers())
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = f"{BASE}{ENTRANCECAR_REFERER}"
        payload = {"pageNo": str(page_no), "rows": str(rows)}
        url = f"{BASE}{ENTRANCECAR_LIST_PATH}"
        # Prime cookies and referer page
        try:
            async with self._session.get(f"{BASE}{ENTRANCECAR_REFERER}", headers=common_headers(), timeout=DEFAULT_TIMEOUT) as r:
                _LOGGER.debug("Prime entrance car GET %s -> %s", ENTRANCECAR_REFERER, r.status)
        except Exception as e:
            _LOGGER.debug("Prime entrance car failed: %s", e)

        _LOGGER.debug("entrancecar_list POST %s body=%s", url, payload)
        async with self._session.post(url, headers=headers, data=payload, timeout=DEFAULT_TIMEOUT) as resp:
            if resp.status == 401:
                _LOGGER.debug("Got 401, attempting re-authentication")
                if await self._maybe_reauth():
                    return await self.async_entrancecar_list(page_no=page_no, rows=rows)
                else:
                    raise ApiError("Authentication failed after retry")
            txt = await resp.text()
            if resp.status != 200:
                raise ApiError(f"entrancecar_list HTTP {resp.status}: {txt[:160]}")
            try:
                data = json.loads(txt)
                self._mark_successful_request()  # Mark successful request
            except Exception as ex:
                _LOGGER.error("entrancecar_list invalid JSON: %s", ex)
                return {"result": 0, "contents": [], "exist_next": False, "page_no": str(page_no), "rows": str(rows)}
            if isinstance(data, dict):
                # Normalize fields
                contents = data.get("contents") or []
                exist_next = bool(data.get("exist_next"))
                page_no_s = str(data.get("page_no") or data.get("pageNo") or str(page_no))
                rows_s = str(data.get("rows") or str(rows))
                return {"result": data.get("result", 1), "contents": contents, "exist_next": exist_next, "page_no": page_no_s, "rows": rows_s}
            return {"result": 0, "contents": [], "exist_next": False, "page_no": str(page_no), "rows": str(rows)}

    async def async_visitor_image_b64(self, file_name: str) -> Optional[str]:
        await self._prime_visitor()
        headers = dict(ajax_headers())
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = f"{BASE}{VISITOR_REFERER}"
        headers["Origin"] = BASE
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["DNT"] = "1"
        headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
        payload = {"file_name": file_name}
        url = f"{BASE}{VISITOR_CONTENT_PATH}"
        _LOGGER.debug("visitor_content (b64) POST %s body=%s", url, payload)
        try:
            async with self._session.post(url, headers=headers, data=payload, timeout=DEFAULT_TIMEOUT) as resp:
                if resp.status == 401:
                    if await self._maybe_reauth():
                        return await self.async_visitor_image_b64(file_name)
                txt = await resp.text()
                if resp.status != 200:
                    _LOGGER.error("Image b64 fetch failed for %s: HTTP %s - %s", file_name, resp.status, (txt or "")[:160])
                    return None
                data = json.loads(txt)
        except Exception as ex:
            _LOGGER.error("Image b64 fetch exception for %s: %s", file_name, ex)
            return None
        b64 = data.get("image") if isinstance(data, dict) else None
        if not b64:
            _LOGGER.error("Image b64 fetch missing 'image' for %s: %s", file_name, data)
            return None
        if "," in b64:
            b64 = b64.split(",", 1)[-1]
        return b64

    async def async_visitor_image_bytes(self, file_name: str) -> Optional[bytes]:
        await self._prime_visitor()
        headers = dict(ajax_headers())
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["Referer"] = f"{BASE}{VISITOR_REFERER}"
        headers["Origin"] = BASE
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["DNT"] = "1"
        headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
        payload = {"file_name": file_name}
        url = f"{BASE}{VISITOR_CONTENT_PATH}"
        _LOGGER.debug("visitor_content POST %s body=%s", url, payload)
        async with self._session.post(url, headers=headers, data=payload, timeout=DEFAULT_TIMEOUT) as resp:
            if resp.status == 401:
                if await self._maybe_reauth():
                    return await self.async_visitor_image_bytes(file_name)
            txt = await resp.text()
            if resp.status != 200:
                _LOGGER.error("Image fetch failed for %s: HTTP %s - %s", file_name, resp.status, (txt or "")[:160])
                return None
            try:
                data = json.loads(txt)
            except Exception as ex:
                _LOGGER.error("Image fetch invalid JSON for %s: %s", file_name, ex)
                return None
            b64 = data.get("image") if isinstance(data, dict) else None
            if not b64:
                _LOGGER.error("Image fetch missing 'image' for %s: %s", file_name, data)
                return None
            if "," in b64:
                b64 = b64.split(",", 1)[-1]
            try:
                return base64.b64decode(b64, validate=False)
            except Exception as ex:
                _LOGGER.error("Image fetch base64 decode error for %s: %s", file_name, ex)
                return None

    async def _prime_visitor(self) -> None:
        try:
            url = f"{BASE}{VISITOR_REFERER}"
            async with self._session.get(url, headers={"Accept": "text/html,application/xhtml+xml"}, timeout=DEFAULT_TIMEOUT) as r:
                _ = await r.text()
                _LOGGER.debug("Prime visitor GET %s -> %s", url, r.status)
        except Exception as e:
            _LOGGER.debug("Prime visitor failed: %s", e)

    # ---------- SockJS helper ----------
    def _outer_array_of(self, obj: Dict[str, Any]) -> str:
        return json.dumps([json.dumps(obj, separators=(",", ":"), ensure_ascii=False)], separators=(",", ":"), ensure_ascii=False)

    def _build_publish_payload(self, address: str, body: Dict[str, Any]) -> str:
        inner_body = {
            "id": body.get("id", self._dev_id or self._username or "homeassistant"),
            "remote_addr": body.get("remote_addr", self._remote_addr or "127.0.0.1"),
            "request": body["request"],
        }
        for k in ("number", "onoff", "brightness", "zone", "temp"):
            if k in body:
                inner_body[k] = str(body[k])
        envelope = {
            "type": "publish",
            "address": str(address),
            "body": json.dumps(inner_body, separators=(",", ":"), ensure_ascii=False),
        }
        payload = self._outer_array_of(envelope)
        _LOGGER.debug("SockJS payload (lights/heaters): %s", payload)
        return payload

    def _build_register_payload(self, address: str) -> str:
        env = {"type": "register", "address": str(address)}
        payload = self._outer_array_of(env)
        _LOGGER.debug("SockJS register payload: %s", payload)
        return payload

    def _build_login_payload(self) -> str:
        username = self._dev_id or self._username or "homeassistant"
        # Use actual password from credentials instead of hardcoded value
        password = self._creds[1] if self._creds and len(self._creds) > 1 else "cvnet"
        envelope = {"type": "send", "address": "vertx.basicauthmanager.login", "body": {"username": username, "password": password}}
        payload = self._outer_array_of(envelope)
        _LOGGER.debug("SockJS login payload: %s", payload)
        return payload

    async def _ensure_ws(self, force_new: bool = False) -> aiohttp.ClientWebSocketResponse:
        """Ensure WebSocket connection is established and ready.
        
        Args:
            force_new: Force creation of new connection even if existing one is available
            
        Returns:
            Active WebSocket connection
            
        Raises:
            ConnectionError: If connection cannot be established
        """
        if not force_new and self._ws and not self._ws.closed:
            return self._ws
            
        # Clean up existing connection
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception as e:
                _LOGGER.debug("Error closing existing WS connection: %s", e)
                
        try:
            await self.async_device_info("0x12")
        except Exception as e:
            _LOGGER.warning("device_info during WS ensure failed: %s", e)
            
        ws_base = self._ws_base or DEFAULT_WS_BASE
        server_id = f"{random.randint(0, 999):03d}"
        session_id = secrets.token_hex(4)
        self._sockjs_server = server_id
        self._sockjs_session = session_id
        ws_url = f"{ws_base}/{server_id}/{session_id}/websocket"
        
        _LOGGER.debug("Opening WS %s", ws_url)
        
        try:
            ws = await self._session.ws_connect(
                ws_url,
                headers=ws_headers(),
                timeout=10,
                autoclose=True,
                autoping=True,
                heartbeat=20,
                ssl=True,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to establish WebSocket connection: {e}")
            
        try:
            msg = await ws.receive(timeout=5)
            _LOGGER.debug("WS first frame: %s", getattr(msg, "data", None))
            if msg.type != WSMsgType.TEXT or not (msg.data or "").lstrip().startswith("o"):
                await ws.close()
                raise ConnectionError(f"WS open failed: {msg.type} {getattr(msg,'data', '')!s}")
        except asyncio.TimeoutError:
            await ws.close()
            raise ConnectionError("WebSocket connection timeout on initial frame")
            
        # Send login payload
        try:
            await ws.send_str(self._build_login_payload())
            try:
                reply = await ws.receive(timeout=2.0)
                _LOGGER.debug("WS login reply frame type=%s data=%s", reply.type, getattr(reply, "data", None))
            except asyncio.TimeoutError:
                _LOGGER.debug("WS login reply: timeout (ignored)")
        except Exception as e:
            await ws.close()
            raise ConnectionError(f"WS login failed: {e}")
            
        self._registered.clear()
        self._ws = ws
        return ws

    async def _ensure_registered(self, address: str) -> None:
        if address in self._registered:
            return
        ws = await self._ensure_ws()
        await ws.send_str(self._build_register_payload(address))
        self._registered.add(address)
        _LOGGER.debug("WS registered address %s", address)

    async def _xhr_send(self, payload_text: str) -> None:
        ws_base = self._ws_base or DEFAULT_WS_BASE
        http_base = ws_base.replace("wss://", "https://").replace("ws://", "http://")
        server_id = self._sockjs_server or "360"
        session_id = self._sockjs_session or "bd2f77ce"
        url = f"{http_base}/{server_id}/{session_id}/xhr_send"
        headers = {
            "Accept": "*/*",
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": BASE,
            "Referer": BASE + "/",
            "User-Agent": UA,
        }
        _LOGGER.debug("XHR_SEND POST %s payload(len)=%s", url, len(payload_text))
        async with self._session.post(url, data=payload_text, headers=headers, timeout=DEFAULT_TIMEOUT) as resp:
            txt = await resp.text()
            _LOGGER.debug("XHR_SEND HTTP %s (first 120): %s", resp.status, (txt or "")[:120])

    async def async_publish(self, address: str, body: dict) -> dict:
        payload_text = self._build_publish_payload(str(address), body)
        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                await self._prime_cookies()
                await self._ensure_ws(force_new=(attempt > 0))
                await self._ensure_registered(str(address))
                await self._ws.send_str(payload_text)
                _LOGGER.debug("Publish sent on WS (attempt %s)", attempt + 1)
                try:
                    msg = await self._ws.receive(timeout=1.0)
                    _LOGGER.debug("WS post-publish frame: type=%s data=%s", msg.type, getattr(msg, "data", None))
                except asyncio.TimeoutError:
                    _LOGGER.debug("WS post-publish: no immediate reply")
                try:
                    await self._xhr_send(payload_text)
                except Exception as e:
                    _LOGGER.debug("XHR_SEND fallback failed (ignored): %s", e)
                return {}
            except (ServerDisconnectedError, ClientError, ApiError, asyncio.TimeoutError) as e:
                _LOGGER.debug("Publish attempt %s failed: %s", attempt + 1, e)
                last_err = e
                if self._ws and not self._ws.closed:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass
                self._ws = None
                continue
        raise ApiError(str(last_err) if last_err else "Publish failed")

    async def async_status_snapshot(self, address: str = "22") -> dict:
        payload_text = self._build_publish_payload(str(address), {"request": "status"})
        try:
            await self._ensure_registered(str(address))
            await self._ws.send_str(payload_text)
            for _ in range(6):
                msg = await self._ws.receive(timeout=2.0)
                _LOGGER.debug("WS status frame: type=%s data=%s", msg.type, getattr(msg, "data", None))
                if msg.type == WSMsgType.TEXT and isinstance(msg.data, str) and msg.data.startswith("a["):
                    try:
                        arr = json.loads(msg.data[1:])
                        if not arr:
                            continue
                        inner = arr[0]
                        data = json.loads(inner) if isinstance(inner, str) else inner
                        body = data.get("body")
                        if isinstance(body, str):
                            try:
                                data["body"] = json.loads(body)
                            except Exception:
                                pass
                        return data
                    except Exception:
                        continue
        except Exception as e:
            _LOGGER.debug("status_snapshot failed: %s", e)
            return {}
        return {}

    async def async_close(self):
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._owns_session:
            await self._session.close()

    async def _maybe_reauth(self) -> bool:
        """Attempt to re-authenticate on 401 if we have cached credentials.

        Returns True if re-auth succeeded.
        """
        if not self._creds:
            return False
        try:
            await self.async_login(*self._creds)
            return True
        except Exception as e:
            _LOGGER.debug("Re-auth failed: %s", e)
            return False
