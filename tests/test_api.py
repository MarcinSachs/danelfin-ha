"""Standalone tests for Danelfin API client.

Run with:
    python test_api.py

These tests validate that `custom_components/danelfin/api.py`:
- sends API requests with the expected headers,
- parses `/ranking` payloads into normalized sensor data,
- returns sectors/industries lists,
- maps HTTP errors into dedicated exceptions.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMP_DIR = PROJECT_ROOT / "custom_components" / "danelfin"
PKG = "custom_components.danelfin"

# Stub Home Assistant and aiohttp dependencies used by api.py.
if "aiohttp" not in sys.modules:
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientSession = object
    aiohttp.ClientTimeout = object
    aiohttp.ContentTypeError = type("ContentTypeError", (Exception,), {})
    aiohttp.ClientError = type("ClientError", (Exception,), {})
    sys.modules["aiohttp"] = aiohttp

for package_name in ("custom_components", "custom_components.danelfin"):
    if package_name not in sys.modules:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(COMP_DIR)] if package_name == PKG else [str(PROJECT_ROOT / "custom_components")]
        sys.modules[package_name] = pkg

spec = importlib.util.spec_from_file_location(
    f"{PKG}.api", COMP_DIR / "api.py",
    submodule_search_locations=[str(COMP_DIR)],
)
api = importlib.util.module_from_spec(spec)
api.__package__ = PKG
sys.modules[f"{PKG}.api"] = api
spec.loader.exec_module(api)

DanelfinApiClient = api.DanelfinApiClient
DanelfinApiError = api.DanelfinApiError
DanelfinAuthError = api.DanelfinAuthError
DanelfinBadRequestError = api.DanelfinBadRequestError
DanelfinRateLimitError = api.DanelfinRateLimitError
DanelfinServerError = api.DanelfinServerError


class DummyResponse:
    def __init__(self, status: int, json_data: Any, text_data: str | None = None) -> None:
        self.status = status
        self._json_data = json_data
        self._text_data = text_data if text_data is not None else ""

    async def text(self) -> str:
        return self._text_data

    async def json(self, content_type: str | None = None) -> Any:
        return self._json_data

    async def __aenter__(self) -> "DummyResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class DummySession:
    def __init__(self, response: DummyResponse) -> None:
        self._response = response
        self.last_request: dict[str, Any] | None = None

    def get(self, url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None):
        self.last_request = {"url": url, "params": params, "headers": headers}
        return self._response


def test_ranking_ticker_response() -> None:
    response_payload = {
        "date": {
            "aiscore": 10,
            "fundamental": 9,
            "technical": 10,
            "sentiment": 10,
            "low_risk": 8,
        }
    }
    session = DummySession(DummyResponse(200, response_payload, text_data="{}"))
    client = DanelfinApiClient("test-key", session=session)

    result = asyncio.run(client.async_get_ranking(ticker="NVDA"))

    assert result == {
        "NVDA": {
            "ai_score": 10,
            "fundamental_score": 9,
            "technical_score": 10,
            "sentiment_score": 10,
            "risk_score": 8,
            "rating": "Strong Buy",
        }
    }
    assert session.last_request is not None
    assert session.last_request["params"]["ticker"] == "NVDA"
    assert session.last_request["headers"]["x-api-key"] == "test-key"


def test_sectors_and_industries() -> None:
    sectors_payload = [{"sector": "energy"}, {"sector": "materials"}]
    industries_payload = [
        {"industry": "aerospace-defense"},
        {"industry": "airlines"},
    ]

    client = DanelfinApiClient("test-key", session=DummySession(DummyResponse(200, sectors_payload, text_data="[]")))
    assert asyncio.run(client.async_get_sectors()) == ["energy", "materials"]

    client = DanelfinApiClient("test-key", session=DummySession(DummyResponse(200, industries_payload, text_data="[]")))
    assert asyncio.run(client.async_get_industries()) == ["aerospace-defense", "airlines"]


def test_error_mapping() -> None:
    cases = [
        (401, DanelfinAuthError),
        (403, DanelfinAuthError),
        (429, DanelfinRateLimitError),
        (400, DanelfinBadRequestError),
        (500, DanelfinServerError),
    ]

    for status, expected_exception in cases:
        client = DanelfinApiClient(
            "test-key",
            session=DummySession(DummyResponse(status, {"error": "fail"}, text_data="error")),
        )
        try:
            asyncio.run(client.async_get_sectors())
            raise AssertionError(f"Expected {expected_exception.__name__} for status {status}")
        except expected_exception:
            pass


def test_invalid_ranking_response_raises() -> None:
    session = DummySession(DummyResponse(200, ["unexpected"], text_data="[]"))
    client = DanelfinApiClient("test-key", session=session)

    try:
        asyncio.run(client.async_get_ranking(ticker="NVDA"))
        raise AssertionError("Expected DanelfinApiError for invalid ranking response")
    except DanelfinApiError:
        pass


async def main() -> None:
    tests = [
        test_ranking_ticker_response,
        test_sectors_and_industries,
        test_error_mapping,
        test_invalid_ranking_response_raises,
    ]

    for test in tests:
        await test()
        print(f"PASS: {test.__name__}")

    print("All Danelfin API client tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
