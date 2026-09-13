"""
Local NIFTY option instrument lookup, built from Angel One's scrip
master file -- same approach as the chart pattern app's local
instrument search (preferred over the live searchScrip endpoint,
per your existing notes on its reliability).
"""
import json
import os
import time

import requests

import config

_cache = {"rows": None, "loaded_at": 0}


def _load_scrip_master():
    if os.path.exists(config.SCRIP_MASTER_CACHE):
        age_hours = (time.time() - os.path.getmtime(config.SCRIP_MASTER_CACHE)) / 3600
        if age_hours < config.SCRIP_MASTER_MAX_AGE_HOURS:
            with open(config.SCRIP_MASTER_CACHE) as f:
                return json.load(f)

    resp = requests.get(config.SCRIP_MASTER_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    with open(config.SCRIP_MASTER_CACHE, "w") as f:
        json.dump(data, f)
    return data


def _nifty_option_rows():
    stale = (time.time() - _cache["loaded_at"]) > config.SCRIP_MASTER_MAX_AGE_HOURS * 3600
    if _cache["rows"] is None or stale:
        all_instruments = _load_scrip_master()
        _cache["rows"] = [
            row for row in all_instruments
            if row.get("name") == "NIFTY"
            and row.get("instrumenttype") == "OPTIDX"
            and row.get("exch_seg") == "NFO"
        ]
        _cache["loaded_at"] = time.time()
    return _cache["rows"]


def _nifty_future_rows():
    stale = (time.time() - _cache.get("fut_loaded_at", 0)) > config.SCRIP_MASTER_MAX_AGE_HOURS * 3600
    if _cache.get("fut_rows") is None or stale:
        all_instruments = _load_scrip_master()
        _cache["fut_rows"] = [
            row for row in all_instruments
            if row.get("name") == "NIFTY"
            and row.get("instrumenttype") == "FUTIDX"
            and row.get("exch_seg") == "NFO"
        ]
        _cache["fut_loaded_at"] = time.time()
    return _cache["fut_rows"]


def get_expiries():
    """Sorted list of NIFTY option expiry date strings, e.g. '25APR2024'."""
    rows = _nifty_option_rows()
    return sorted(
        set(r["expiry"] for r in rows),
        key=lambda d: time.strptime(d, "%d%b%Y"),
    )


def get_next_expiry(expiry):
    """The expiry immediately after `expiry` in the sorted expiry list --
    the 'back month' leg for calendar/diagonal spreads. Returns None if
    `expiry` is the furthest one currently listed."""
    expiries = get_expiries()
    if expiry not in expiries:
        return None
    idx = expiries.index(expiry)
    return expiries[idx + 1] if idx + 1 < len(expiries) else None


def get_front_month_future():
    """Nearest-expiry NIFTY futures contract: {'token', 'symbol', 'expiry'}.
    Used as the underlying leg for covered/protective/synthetic strategies
    (there's no 'NIFTY stock' to buy directly, so index strategies use the
    front-month future as the underlying position)."""
    rows = _nifty_future_rows()
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda r: time.strptime(r["expiry"], "%d%b%Y"))
    r = rows_sorted[0]
    return {"token": r["token"], "symbol": r["symbol"], "expiry": r["expiry"]}


def get_chain_tokens(expiry):
    """Returns {strike_in_rupees: {'CE': {token, symbol}, 'PE': {token, symbol}}}
    for the given expiry."""
    rows = _nifty_option_rows()
    chain = {}
    for r in rows:
        if r["expiry"] != expiry:
            continue
        strike = int(float(r["strike"]) / 100)  # scrip master stores strike * 100; NIFTY strikes are always whole rupees
        opt_type = "CE" if r["symbol"].endswith("CE") else "PE"
        chain.setdefault(strike, {})[opt_type] = {
            "token": r["token"],
            "symbol": r["symbol"],
        }
    return chain
