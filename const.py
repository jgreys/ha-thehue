from __future__ import annotations

DOMAIN = "cvnet"

# Base URLs and defaults
BASE = "https://js-thehue.uasis.com"
DEFAULT_TIMEOUT_S = 10  # seconds
DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_VISITOR_ROWS = 5
DEFAULT_CAR_ROWS = 5
MAX_VISITOR_ATTRIBUTES = 8  # Limit for state attributes to avoid 16KB cap
SESSION_TIMEOUT_HOURS = 24  # Consider session expired after this many hours

# User agent string
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
)

# Paths
VISITOR_LIST_PATH = "/cvnet/web/visitor_list.do"
VISITOR_CONTENT_PATH = "/cvnet/web/visitor_content.do"
VISITOR_REFERER = "/cvnet/web/absence_visitor.view"

# Car entries (entrance) paths
ENTRANCECAR_LIST_PATH = "/cvnet/web/entrancecar_list.do"
ENTRANCECAR_REFERER = "/cvnet/web/enter_car.view"

# WebSocket/SockJS
DEFAULT_WS_BASE = "wss://js-thehue.uasis.com:9099/devicecontrol"


def common_headers() -> dict:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Origin": BASE,
        "Referer": BASE + "/",
        "User-Agent": UA,
    }


def ajax_headers() -> dict:
    h = common_headers()
    h.update({
        "AJAX": "true",
        "X-Requested-With": "XMLHttpRequest",
    })
    return h


def ws_headers() -> dict:
    return {
        "Accept": "*/*",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Origin": BASE,
        "Referer": BASE + "/",
        "User-Agent": UA,
    }
