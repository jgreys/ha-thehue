"""Tests for the CVNET coordinator."""
from __future__ import annotations

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from cvnet.core.coordinator import CvnetCoordinator
from cvnet.const import (
    DEFAULT_UPDATE_INTERVAL, DEFAULT_VISITOR_ROWS, DEFAULT_CAR_ROWS,
    CONF_UPDATE_INTERVAL, CONF_VISITOR_ROWS, CONF_CAR_ROWS,
)


@pytest.fixture
def coordinator(mock_hass, mock_entry):
    """Create a CvnetCoordinator with mocked HA and entry."""
    with patch("cvnet.core.coordinator.async_get_clientsession", return_value=MagicMock()):
        coord = CvnetCoordinator(mock_hass, mock_entry)
    coord.client = MagicMock()
    coord.client.async_login = AsyncMock()
    coord.client.async_visitor_list = AsyncMock(return_value=[])
    coord.client.async_entrancecar_list = AsyncMock(return_value={
        "contents": [], "exist_next": False, "page_no": "1", "rows": "5"
    })
    coord.client.async_status_snapshot = AsyncMock(return_value={})
    coord.client.async_telemetering = AsyncMock(return_value={})
    coord.client._creds = ("testuser", "testpass")
    coord.async_request_refresh = AsyncMock()
    return coord


class TestCoordinatorInit:
    def test_default_interval(self, mock_hass, mock_entry):
        with patch("cvnet.core.coordinator.async_get_clientsession"):
            coord = CvnetCoordinator(mock_hass, mock_entry)
        assert coord.update_interval == timedelta(seconds=DEFAULT_UPDATE_INTERVAL)

    def test_default_rows(self, mock_hass, mock_entry):
        with patch("cvnet.core.coordinator.async_get_clientsession"):
            coord = CvnetCoordinator(mock_hass, mock_entry)
        assert coord._visitor_rows == DEFAULT_VISITOR_ROWS
        assert coord._car_rows == DEFAULT_CAR_ROWS

    def test_options_override_interval(self, mock_hass, mock_entry):
        mock_entry.options = {CONF_UPDATE_INTERVAL: 30}
        with patch("cvnet.core.coordinator.async_get_clientsession"):
            coord = CvnetCoordinator(mock_hass, mock_entry)
        assert coord.update_interval == timedelta(seconds=30)

    def test_options_override_rows(self, mock_hass, mock_entry):
        mock_entry.options = {CONF_VISITOR_ROWS: 10, CONF_CAR_ROWS: 20}
        with patch("cvnet.core.coordinator.async_get_clientsession"):
            coord = CvnetCoordinator(mock_hass, mock_entry)
        assert coord._visitor_rows == 10
        assert coord._car_rows == 20


class TestApplyOptions:
    def test_apply_options_updates_interval(self, coordinator):
        coordinator.apply_options({CONF_UPDATE_INTERVAL: 60})
        assert coordinator.update_interval == timedelta(seconds=60)

    def test_apply_options_updates_rows(self, coordinator):
        coordinator.apply_options({CONF_VISITOR_ROWS: 15, CONF_CAR_ROWS: 25})
        assert coordinator._visitor_rows == 15
        assert coordinator._car_rows == 25

    def test_apply_options_resets_pagination(self, coordinator):
        coordinator._visitor_page_no = 3
        coordinator._car_page_no = 5
        coordinator.apply_options({})
        assert coordinator._visitor_page_no == 1
        assert coordinator._car_page_no == 1


class TestPagination:
    async def test_visitor_next_page(self, coordinator):
        coordinator._visitor_exist_next = True
        await coordinator.async_visitor_next_page()
        assert coordinator._visitor_page_no == 2

    async def test_visitor_next_page_blocked(self, coordinator):
        coordinator._visitor_exist_next = False
        await coordinator.async_visitor_next_page()
        assert coordinator._visitor_page_no == 1

    async def test_visitor_prev_page(self, coordinator):
        coordinator._visitor_page_no = 3
        await coordinator.async_visitor_prev_page()
        assert coordinator._visitor_page_no == 2

    async def test_visitor_prev_page_at_one(self, coordinator):
        coordinator._visitor_page_no = 1
        await coordinator.async_visitor_prev_page()
        assert coordinator._visitor_page_no == 1

    async def test_car_next_page(self, coordinator):
        coordinator._car_exist_next = True
        await coordinator.async_car_next_page()
        assert coordinator._car_page_no == 2

    async def test_car_next_page_blocked(self, coordinator):
        coordinator._car_exist_next = False
        await coordinator.async_car_next_page()
        assert coordinator._car_page_no == 1

    async def test_car_prev_page(self, coordinator):
        coordinator._car_page_no = 3
        await coordinator.async_car_prev_page()
        assert coordinator._car_page_no == 2

    async def test_car_prev_page_at_one(self, coordinator):
        coordinator._car_page_no = 1
        await coordinator.async_car_prev_page()
        assert coordinator._car_page_no == 1

    async def test_set_visitor_rows_resets_page(self, coordinator):
        coordinator._visitor_page_no = 5
        await coordinator.async_visitor_set_rows(10)
        assert coordinator._visitor_rows == 10
        assert coordinator._visitor_page_no == 1

    async def test_set_car_rows_resets_page(self, coordinator):
        coordinator._car_page_no = 5
        await coordinator.async_car_set_rows(20)
        assert coordinator._car_rows == 20
        assert coordinator._car_page_no == 1


class TestNewVisitorDetection:
    async def test_first_run_skips_notification(self, coordinator, mock_hass):
        coordinator._first_run = True
        coordinator._visitor_list = [
            {"file_name": "img1.jpg", "date_time": "2025-01-01", "title": "Visitor 1"},
        ]
        await coordinator._check_new_visitors()
        mock_hass.bus.async_fire.assert_not_called()
        # But seen set should be populated
        assert "img1.jpg" in coordinator._seen_visitors

    async def test_fires_event_on_new_visitor(self, coordinator, mock_hass):
        coordinator._first_run = False
        coordinator._seen_visitors = {"old.jpg"}
        coordinator._visitor_list = [
            {"file_name": "old.jpg", "date_time": "2025-01-01", "title": "old"},
            {"file_name": "new.jpg", "date_time": "2025-01-02", "title": "new"},
        ]
        await coordinator._check_new_visitors()
        mock_hass.bus.async_fire.assert_called_once()
        args = mock_hass.bus.async_fire.call_args
        assert args[0][0] == "cvnet_new_visitor"
        assert args[0][1]["file_name"] == "new.jpg"

    async def test_selects_new_visitor(self, coordinator, mock_hass):
        coordinator._first_run = False
        coordinator._seen_visitors = {"old.jpg"}
        coordinator._visitor_list = [
            {"file_name": "new.jpg", "date_time": "2025-01-02", "title": "new"},
        ]
        await coordinator._check_new_visitors()
        assert coordinator._selected == "new.jpg"

    async def test_no_event_when_no_new_visitors(self, coordinator, mock_hass):
        coordinator._first_run = False
        coordinator._seen_visitors = {"img1.jpg"}
        coordinator._visitor_list = [
            {"file_name": "img1.jpg", "date_time": "2025-01-01", "title": "same"},
        ]
        await coordinator._check_new_visitors()
        mock_hass.bus.async_fire.assert_not_called()


class TestNewCarDetection:
    async def test_first_run_skips_notification(self, coordinator, mock_hass):
        coordinator._first_run = True
        coordinator._car_contents = [
            {"title": "12가3456", "date_time": "2025-01-01 10:00", "inout": "0"},
        ]
        await coordinator._check_new_car_entries()
        mock_hass.bus.async_fire.assert_not_called()
        assert len(coordinator._seen_cars) == 1

    async def test_fires_event_on_new_car(self, coordinator, mock_hass):
        coordinator._first_run = False
        coordinator._seen_cars = {"12가3456_2025-01-01 10:00"}
        coordinator._car_contents = [
            {"title": "12가3456", "date_time": "2025-01-01 10:00", "inout": "0"},
            {"title": "78나9012", "date_time": "2025-01-01 11:00", "inout": "1"},
        ]
        await coordinator._check_new_car_entries()
        mock_hass.bus.async_fire.assert_called_once()
        args = mock_hass.bus.async_fire.call_args
        assert args[0][0] == "cvnet_car_entry"
        assert args[0][1]["plate"] == "78나9012"
        assert args[0][1]["direction"] == "exited"

    async def test_car_entered_direction(self, coordinator, mock_hass):
        coordinator._first_run = False
        coordinator._seen_cars = set()
        coordinator._car_contents = [
            {"title": "12가3456", "date_time": "2025-01-01 10:00", "inout": "0"},
        ]
        await coordinator._check_new_car_entries()
        args = mock_hass.bus.async_fire.call_args
        assert args[0][1]["direction"] == "entered"


class TestSessionInfo:
    def test_get_session_info(self, coordinator):
        coordinator.client._creds = ("testuser", "testpass")
        coordinator.client._username = "testuser"
        coordinator.client._last_successful_request = None
        coordinator.client._is_session_expired = lambda: True
        info = coordinator.get_session_info()
        assert info["has_credentials"] is True
        assert info["username"] == "testuser"
        assert info["session_expired"] is True
