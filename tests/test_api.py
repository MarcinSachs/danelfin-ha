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

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMP_DIR = PROJECT_ROOT / "custom_components" / "danelfin"
PKG = "custom_components.danelfin"

# ---------------------------------------------------------------------------
# Real aiohttp — save reference BEFORE any stubbing so live tests can use it.
# ---------------------------------------------------------------------------
try:
    import aiohttp as _real_aiohttp  # noqa: PLC0415
except ImportError:
    _real_aiohttp = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Load API key from .env (no external deps required)
# ---------------------------------------------------------------------------


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


_API_KEY: str = _load_env(PROJECT_ROOT / ".env").get("API_KEY", "")

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
        pkg.__path__ = [str(COMP_DIR)] if package_name == PKG else [
            str(PROJECT_ROOT / "custom_components")]
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

# Constants used by live tests (loaded transitively with api.py via const.py)
_const = sys.modules.get(f"{PKG}.const")
MARKET_US: str = getattr(_const, "MARKET_US", "us")
MARKET_ETF: str = getattr(_const, "MARKET_ETF", "etf")


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
    # Real API returns date strings as keys (descending order); parser picks the first.
    response_payload = {
        "2026-04-11": {
            "aiscore": 10,
            "fundamental": 9,
            "technical": 10,
            "sentiment": 10,
            "low_risk": 8,
        },
        "2026-04-10": {
            "aiscore": 8,
            "fundamental": 7,
            "technical": 8,
            "sentiment": 7,
            "low_risk": 6,
        },
    }
    session = DummySession(DummyResponse(
        200, response_payload, text_data="{}"))
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

    client = DanelfinApiClient(
        "test-key", session=DummySession(DummyResponse(200, sectors_payload, text_data="[]")))
    assert asyncio.run(client.async_get_sectors()) == ["energy", "materials"]

    client = DanelfinApiClient(
        "test-key", session=DummySession(DummyResponse(200, industries_payload, text_data="[]")))
    assert asyncio.run(client.async_get_industries()) == [
        "aerospace-defense", "airlines"]


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
            session=DummySession(DummyResponse(
                status, {"error": "fail"}, text_data="error")),
        )
        try:
            asyncio.run(client.async_get_sectors())
            raise AssertionError(
                f"Expected {expected_exception.__name__} for status {status}")
        except expected_exception:
            pass


def test_invalid_ranking_response_raises() -> None:
    session = DummySession(DummyResponse(200, ["unexpected"], text_data="[]"))
    client = DanelfinApiClient("test-key", session=session)

    try:
        asyncio.run(client.async_get_ranking(ticker="NVDA"))
        raise AssertionError(
            "Expected DanelfinApiError for invalid ranking response")
    except DanelfinApiError:
        pass


def test_ranking_top_etf_injects_date() -> None:
    """When no ticker is given, the client must inject a date (API requirement).

    Verifies the fix for Top ETFs / Top US Stocks sensors being unavailable:
    previously, only the EU market got an auto-injected date.
    """
    response_payload = {
        "2026-04-14": {
            "QQQ": {"aiscore": 9, "fundamental": 8, "technical": 9, "sentiment": 8, "low_risk": 7},
            "SPY": {"aiscore": 8, "fundamental": 7, "technical": 8, "sentiment": 7, "low_risk": 6},
        }
    }
    session = DummySession(DummyResponse(
        200, response_payload, text_data="{}"))
    client = DanelfinApiClient("test-key", session=session)

    result = asyncio.run(client.async_get_ranking(
        market=MARKET_US, asset=MARKET_ETF))

    # date must be present — without it the API returns HTTP 400
    assert session.last_request is not None
    assert "date" in session.last_request["params"], (
        "date param missing from ETF top-ranking request — API will return 400"
    )
    assert "ticker" not in session.last_request["params"]
    assert session.last_request["params"]["asset"] == MARKET_ETF

    # Response contains ticker-keyed entries
    assert "QQQ" in result
    assert "SPY" in result
    assert result["QQQ"]["ai_score"] == 9
    assert result["QQQ"]["rating"] == "Strong Buy"


# ---------------------------------------------------------------------------
# Live tests — run only when _API_KEY is set and real aiohttp is available
# ---------------------------------------------------------------------------

_EXPECTED_SCORE_KEYS = {
    "ai_score",
    "fundamental_score",
    "technical_score",
    "sentiment_score",
    "risk_score",
    "rating",
}


_need_api_key = pytest.mark.skipif(
    not _API_KEY or _real_aiohttp is None,
    reason="API_KEY not set in .env or aiohttp not installed",
)


@_need_api_key
async def test_live_sectors_returns_list() -> None:
    """GET /sectors returns a non-empty list of sector slugs."""
    async with _real_aiohttp.ClientSession(timeout=_real_aiohttp.ClientTimeout(total=15)) as session:
        client = DanelfinApiClient(_API_KEY, session=session)
        sectors = await client.async_get_sectors()

    assert isinstance(sectors, list), f"Expected list, got {type(sectors)}"
    assert len(sectors) > 0, "Sectors list is empty"
    assert all(isinstance(s, str)
               for s in sectors), "All sectors should be strings"
    print(f"      sectors ({len(sectors)}): {sectors[:5]} …")


@_need_api_key
async def test_live_ranking_us_stock() -> None:
    """GET /ranking for NVDA returns a ticker-keyed dict with the latest scores."""
    async with _real_aiohttp.ClientSession(timeout=_real_aiohttp.ClientTimeout(total=15)) as session:
        client = DanelfinApiClient(_API_KEY, session=session)
        result = await client.async_get_ranking(ticker="NVDA", market=MARKET_US)

    assert "NVDA" in result, (
        f"Expected 'NVDA' key (latest date picked by parser), got: {list(result.keys())[:5]}"
    )
    data = result["NVDA"]
    missing = _EXPECTED_SCORE_KEYS - data.keys()
    assert not missing, f"Missing score keys for NVDA: {missing}"
    assert 1 <= data["ai_score"] <= 10, f"ai_score out of range: {data['ai_score']}"
    print(f"      NVDA (latest): {data}")


@_need_api_key
async def test_live_ranking_etf() -> None:
    """GET /ranking for SPY (ETF) returns a ticker-keyed dict with the latest scores."""
    await asyncio.sleep(3)  # avoid 429 when running tests back-to-back
    try:
        async with _real_aiohttp.ClientSession(timeout=_real_aiohttp.ClientTimeout(total=15)) as session:
            client = DanelfinApiClient(_API_KEY, session=session)
            result = await client.async_get_ranking(ticker="SPY", market=MARKET_ETF)
    except DanelfinRateLimitError:
        pytest.skip("Hit rate limit — run again in a moment")

    assert "SPY" in result, (
        f"Expected 'SPY' key (latest date picked by parser), got: {list(result.keys())[:5]}"
    )
    data = result["SPY"]
    missing = _EXPECTED_SCORE_KEYS - data.keys()
    assert not missing, f"Missing score keys for SPY: {missing}"
    print(f"      SPY (latest): {data}")


@_need_api_key
async def test_live_ranking_top_etfs() -> None:
    """GET /ranking with asset=etf and no ticker returns a dict of ETF tickers.

    This is what DanelfinRecommendationsCoordinator calls for Top ETFs.
    Before the fix, this request lacked a required date param and got HTTP 400.
    """
    import asyncio as _asyncio
    await _asyncio.sleep(3)  # avoid 429 when tests run back-to-back
    try:
        async with _real_aiohttp.ClientSession(timeout=_real_aiohttp.ClientTimeout(total=15)) as session:
            client = DanelfinApiClient(_API_KEY, session=session)
            result = await client.async_get_ranking(market=MARKET_US, asset=MARKET_ETF)
    except DanelfinRateLimitError:
        pytest.skip("Hit rate limit — run again in a moment")

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert len(result) > 0, "Top ETF ranking returned empty result"
    sample_ticker = next(iter(result))
    sample_data = result[sample_ticker]
    missing = _EXPECTED_SCORE_KEYS - sample_data.keys()
    assert not missing, f"Missing score keys for {sample_ticker}: {missing}"
    print(
        f"      Top ETF ranking: {len(result)} tickers, sample={sample_ticker}: {sample_data}")


@_need_api_key
async def test_live_invalid_key_auth_error() -> None:
    """A clearly wrong key format should raise DanelfinAuthError (401/403).

    Note: some API gateways return 200 with empty data instead of 401 for
    unrecognised keys. In that case we at least confirm no crash occurs and
    log the actual behaviour.
    """
    async with _real_aiohttp.ClientSession(timeout=_real_aiohttp.ClientTimeout(total=15)) as session:
        client = DanelfinApiClient("invalid-key-xyz", session=session)
        try:
            await client.async_get_sectors()
            # API did not raise — it accepted the key (permissive gateway).
            print("      NOTE: API returned 200 for invalid key (no 401/403 enforced).")
        except DanelfinAuthError:
            pass  # ideal behaviour


def main() -> None:
    # Mock tests are sync functions that call asyncio.run() internally.
    # Keep main() sync to avoid nested event loop errors.
    mock_tests = [
        test_ranking_ticker_response,
        test_sectors_and_industries,
        test_error_mapping,
        test_invalid_ranking_response_raises,
        test_ranking_top_etf_injects_date,
    ]

    # Live tests are async coroutines — each gets its own asyncio.run() call.
    live_tests = [
        test_live_sectors_returns_list,
        test_live_ranking_us_stock,
        test_live_ranking_etf,
        test_live_ranking_top_etfs,
        test_live_invalid_key_auth_error,
    ]

    passed = 0
    failed = 0

    print("=== Mock tests (no API key required) ===")
    for test in mock_tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {test.__name__} — {exc}")
            failed += 1

    print()
    if not _API_KEY:
        print("=== Live tests SKIPPED (no API_KEY in .env) ===")
    elif _real_aiohttp is None:
        print("=== Live tests SKIPPED (aiohttp not installed) ===")
    else:
        print("=== Live tests (real Danelfin API) ===")
        for test in live_tests:
            try:
                print(f"RUN:  {test.__name__}")
                asyncio.run(test())
                print(f"PASS: {test.__name__}")
                passed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {test.__name__} — {exc}")
                failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
