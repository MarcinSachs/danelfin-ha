"""Standalone test for the Danelfin recommendations parser.

Imports _parse_rankings and RANKING_CATEGORIES directly from the integration
so the test always reflects production parser behaviour.

Usage:
    python test_rankings2.py              # test all 3 categories
    python test_rankings2.py eu           # test only EU stocks
    python test_rankings2.py us etf       # test US stocks and ETFs
"""
import importlib.util
import sys
import types
import urllib.request
from pathlib import Path

COMP_DIR = Path(__file__).parent / "custom_components" / "danelfin"
PKG = "custom_components.danelfin"

# ── HA / aiohttp stubs ────────────────────────────────────────────────────────
for _n in ("homeassistant", "homeassistant.core", "homeassistant.helpers",
           "homeassistant.helpers.update_coordinator", "aiohttp"):
    sys.modules.setdefault(_n, types.ModuleType(_n))

sys.modules["homeassistant.core"].HomeAssistant = object
_coord = sys.modules["homeassistant.helpers.update_coordinator"]
_coord.DataUpdateCoordinator = object
_coord.UpdateFailed = Exception
_aio = sys.modules["aiohttp"]
for _attr in ("TCPConnector", "ClientSession", "ClientTimeout"):
    setattr(_aio, _attr, object)
_aio.ClientError = Exception


def _load_pkg_module(name: str):
    """Load integration module under its full package name so relative imports work."""
    full_name = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(
        full_name, COMP_DIR / f"{name}.py",
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PKG
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Register the package itself
_pkg_mod = types.ModuleType(PKG)
_pkg_mod.__path__ = [str(COMP_DIR)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules[PKG] = _pkg_mod

# Load const first (no relative imports inside it)
const = _load_pkg_module("const")
RANKING_CATEGORIES = const.RANKING_CATEGORIES
REQUEST_HEADERS = const.REQUEST_HEADERS
REQUEST_TIMEOUT = const.REQUEST_TIMEOUT

# Load recommendations (uses `from .const import ...`)
rec = _load_pkg_module("recommendations")
_parse_rankings = rec._parse_rankings

# ── CLI helpers ───────────────────────────────────────────────────────────────
_ALIASES = {"eu": "rec_eu", "us": "rec_us", "etf": "rec_etf"}


def fetch(url: str) -> str:
    # Omit Accept-Encoding so the server returns plain (uncompressed) HTML.
    # aiohttp in the production coordinator decompresses automatically;
    # urllib.request used here does not.
    headers = {k: v for k, v in REQUEST_HEADERS.items() if k != "Accept-Encoding"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    args = sys.argv[1:]
    cat_keys = [_ALIASES.get(a.lower(), a) for a in args] if args else list(RANKING_CATEGORIES.keys())

    for cat_key in cat_keys:
        cfg = RANKING_CATEGORIES.get(cat_key)
        if not cfg:
            print(f"Unknown category: {cat_key!r}. Use: eu / us / etf")
            continue

        print(f"\n{'='*60}")
        print(f"  {cfg['label']} ({cat_key})  ->  {cfg['url']}")

        html = fetch(cfg["url"])
        results = _parse_rankings(html, cat_key)

        if not results:
            print("  !! NO RESULTS -- parsing failed")
        else:
            for pos, entry in sorted(results.items()):
                print(
                    f"  #{pos}: {entry['ticker']:12s} | "
                    f"AI={str(entry['ai_score']):>4s} | "
                    f"{entry['rating']:12s} | "
                    f"{entry['company']}"
                )
        print(f"  Total: {len(results)}/5")


if __name__ == "__main__":
    main()
