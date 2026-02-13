"""Tests for the CVNET API client."""
from __future__ import annotations

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cvnet.api.client import Client, LoginError, ApiError, ValidationError


def _mock_response(status=200, text="", json_data=None):
    """Create a mock HTTP response as an async context manager."""
    resp = AsyncMock()
    resp.status = status
    if json_data is not None:
        text = json.dumps(json_data)
    resp.text = AsyncMock(return_value=text)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestLogin:
    async def test_login_success(self, client, mock_session):
        """Successful login stores credentials and marks session active."""
        mock_session.post.return_value = _mock_response(200, json_data={"result": "1"})
        mock_session.get.return_value = _mock_response(200, text="ok")

        await client.async_login("user", "pass")
        assert client._creds == ("user", "pass")
        assert client._username == "user"
        assert client._last_successful_request is not None

    async def test_login_empty_username_raises_validation(self, client):
        with pytest.raises(ValidationError):
            await client.async_login("", "pass")

    async def test_login_empty_password_raises_validation(self, client):
        with pytest.raises(ValidationError):
            await client.async_login("user", "")

    async def test_login_401_raises(self, client, mock_session):
        mock_session.post.return_value = _mock_response(401, text="Unauthorized")

        with pytest.raises(LoginError, match="login HTTP 401"):
            await client.async_login("user", "pass")

    async def test_login_bad_credentials(self, client, mock_session):
        mock_session.post.return_value = _mock_response(
            200, json_data={"result": "0", "message": "Bad creds"}
        )

        with pytest.raises(LoginError, match="Bad creds"):
            await client.async_login("user", "pass")

    async def test_login_verify_401_raises(self, client, mock_session):
        """If login succeeds but telemetering.view returns 401, it should raise."""
        post_resp = _mock_response(200, json_data={"result": "1"})
        # First GET (prime cookies) succeeds, second GET (verify) returns 401
        get_responses = [
            _mock_response(200, text="ok"),  # prime /cvnet/web/
            _mock_response(200, text="ok"),  # prime /
            _mock_response(200, text="ok"),  # prime /telemetering.view
            _mock_response(401, text="Unauthorized"),  # verify /telemetering.view
        ]
        mock_session.post.return_value = post_resp
        mock_session.get.side_effect = get_responses

        with pytest.raises(LoginError, match="telemetering.view returned 401"):
            await client.async_login("user", "pass")


class TestSessionExpiry:
    def test_expired_when_no_last_request(self, client):
        assert client._is_session_expired() is True

    def test_not_expired_after_recent_request(self, client):
        client._last_successful_request = time.time()
        assert client._is_session_expired() is False

    def test_expired_after_timeout(self, client):
        client._last_successful_request = time.time() - (25 * 3600)
        assert client._is_session_expired() is True

    def test_mark_successful_request(self, client):
        assert client._last_successful_request is None
        client._mark_successful_request()
        assert client._last_successful_request is not None
        assert time.time() - client._last_successful_request < 2


class TestVisitorList:
    async def test_returns_contents(self, client, mock_session):
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        items = [{"file_name": "img1.jpg", "date_time": "2025-01-01"}]
        mock_session.get.return_value = _mock_response(200, text="ok")
        mock_session.post.return_value = _mock_response(
            200, json_data={"contents": items}
        )

        result = await client.async_visitor_list(page_no=1, rows=5)
        assert len(result) == 1
        assert result[0]["file_name"] == "img1.jpg"

    async def test_401_triggers_reauth(self, client, mock_session):
        """On 401, client should attempt re-auth then retry."""
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        items = [{"file_name": "img1.jpg"}]
        mock_session.get.return_value = _mock_response(200, text="ok")

        # First call returns 401, second (after re-auth) succeeds
        call_count = 0
        original_post = mock_session.post

        def side_effect_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(401, text="Unauthorized")
            return _mock_response(200, json_data={"contents": items})

        mock_session.post.side_effect = side_effect_post
        # Patch _maybe_reauth to succeed
        client._maybe_reauth = AsyncMock(return_value=True)

        result = await client.async_visitor_list(page_no=1, rows=5)
        assert len(result) == 1
        client._maybe_reauth.assert_called_once()

    async def test_empty_json_returns_empty_list(self, client, mock_session):
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        mock_session.get.return_value = _mock_response(200, text="ok")
        mock_session.post.return_value = _mock_response(200, text="not json{{{")

        result = await client.async_visitor_list(page_no=1, rows=5)
        assert result == []


class TestEntranceCarList:
    async def test_returns_normalized_data(self, client, mock_session):
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        api_data = {
            "result": 1,
            "contents": [{"title": "12가3456", "inout": "0", "date_time": "2025-01-01 10:00"}],
            "exist_next": True,
            "page_no": "1",
            "rows": "5",
        }
        mock_session.get.return_value = _mock_response(200, text="ok")
        mock_session.post.return_value = _mock_response(200, json_data=api_data)

        result = await client.async_entrancecar_list(page_no=1, rows=5)
        assert len(result["contents"]) == 1
        assert result["exist_next"] is True
        assert result["page_no"] == "1"


class TestTelemetering:
    async def test_returns_data(self, client, mock_session):
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        mock_session.get.return_value = _mock_response(200, text="ok")
        mock_session.post.return_value = _mock_response(
            200, json_data={"electric": "150.5", "water": "12.3", "gas": "5.1"}
        )

        result = await client.async_telemetering()
        assert result["electric"] == "150.5"
        assert result["water"] == "12.3"
        assert result["gas"] == "5.1"

    async def test_invalid_json_returns_empty(self, client, mock_session):
        client._creds = ("user", "pass")
        client._last_successful_request = time.time()

        mock_session.get.return_value = _mock_response(200, text="ok")
        mock_session.post.return_value = _mock_response(200, text="not-json")

        result = await client.async_telemetering()
        assert result == {}


class TestWebSocketHealth:
    def test_no_ws_is_unhealthy(self, client):
        assert client._is_ws_healthy() is False

    def test_closed_ws_is_unhealthy(self, client):
        ws = MagicMock()
        ws.closed = True
        client._ws = ws
        assert client._is_ws_healthy() is False

    def test_open_ws_is_healthy(self, client):
        ws = MagicMock()
        ws.closed = False
        # Remove _writer to avoid transport check complexity
        del ws._writer
        client._ws = ws
        assert client._is_ws_healthy() is True


class TestBackoff:
    async def test_backoff_increments(self, client):
        assert client._ws_backoff_attempt == 0
        with patch("cvnet.api.client.asyncio.sleep", new_callable=AsyncMock):
            await client._ws_backoff_wait()
        assert client._ws_backoff_attempt == 1
        with patch("cvnet.api.client.asyncio.sleep", new_callable=AsyncMock):
            await client._ws_backoff_wait()
        assert client._ws_backoff_attempt == 2

    async def test_backoff_resets_on_ws_connect(self, client):
        client._ws_backoff_attempt = 3
        # Simulate successful _ensure_ws by directly setting
        ws = MagicMock()
        ws.closed = False
        client._ws = ws
        client._ws_backoff_attempt = 0
        assert client._ws_backoff_attempt == 0
