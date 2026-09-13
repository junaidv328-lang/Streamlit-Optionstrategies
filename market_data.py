"""
Live market data for NIFTY: spot price and a merged option chain
(Greeks + IV from the Option Greeks API, LTP from the quote API --
they're separate calls, see README for why).

Every parse point below checks the shape it expects before indexing
into it, and raises a RuntimeError with a chunk of the raw response
if it's wrong -- rather than a cryptic "string indices must be
integers" from indexing into something that isn't what we assumed.
These endpoints (especially optionGreek) weren't testable live from
my end, so if one of these fires, the message it gives you is the
fastest way to see the real shape and fix the parsing.
"""
import json

import requests

import angel_auth
import config
import instruments

GREEK_URL = f"{config.BASE_URL}/rest/secure/angelbroking/marketData/v1/optionGreek"
QUOTE_URL = f"{config.BASE_URL}/rest/secure/angelbroking/market/v1/quote/"


def _post(url, payload):
    session = angel_auth.get_session()
    headers = angel_auth.auth_headers(session)
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _expect(value, expected_type, where, raw):
    """Raise a diagnosable error (with the actual raw response attached)
    if `value` isn't the shape we're about to index into."""
    if not isinstance(value, expected_type):
        raise RuntimeError(
            f"{where}: expected {expected_type.__name__}, got {type(value).__name__}. "
            f"Raw response: {json.dumps(raw)[:800]}"
        )
    return value


def get_spot_price():
    payload = {"mode": "LTP", "exchangeTokens": {config.NIFTY_SPOT_EXCHANGE: [config.NIFTY_SPOT_TOKEN]}}
    data = _post(QUOTE_URL, payload)
    body = _expect(data.get("data"), dict, "spot price quote: data['data']", data)
    fetched = _expect(body.get("fetched"), list, "spot price quote: data['data']['fetched']", data)
    if not fetched:
        raise RuntimeError(f"No spot price returned -- check the NIFTY index token is still valid. Raw: {json.dumps(data)[:800]}")
    return float(fetched[0]["ltp"])


def get_vix():
    """Current India VIX LTP -- same quote endpoint as the spot price,
    just a different index token, so it carries the same reliability
    as get_spot_price() (unlike optionGreek, see get_greeks() below)."""
    payload = {"mode": "LTP", "exchangeTokens": {config.VIX_EXCHANGE: [config.VIX_TOKEN]}}
    data = _post(QUOTE_URL, payload)
    body = _expect(data.get("data"), dict, "VIX quote: data['data']", data)
    fetched = _expect(body.get("fetched"), list, "VIX quote: data['data']['fetched']", data)
    if not fetched:
        raise RuntimeError(f"No VIX price returned. Raw: {json.dumps(data)[:800]}")
    return float(fetched[0]["ltp"])


def get_futures_price():
    """Front-month NIFTY futures LTP -- the 'underlying' leg for
    covered/protective/synthetic strategies, since there's no NIFTY
    stock to hold directly."""
    fut = instruments.get_front_month_future()
    if fut is None:
        raise RuntimeError("No NIFTY futures contract found in the instrument master.")
    data = _post(QUOTE_URL, {"mode": "LTP", "exchangeTokens": {"NFO": [fut["token"]]}})
    body = _expect(data.get("data"), dict, "futures quote: data['data']", data)
    fetched = _expect(body.get("fetched"), list, "futures quote: data['data']['fetched']", data)
    if not fetched:
        raise RuntimeError(f"No LTP returned for futures contract {fut['symbol']}. Raw: {json.dumps(data)[:800]}")
    return float(fetched[0]["ltp"]), fut


def get_greeks(expiry):
    """expiry like '25APR2024'. Live/current expiries only -- Angel One
    doesn't serve Greeks for expired contracts.

    NOTE: this specific endpoint has a long-running, widely-reported
    issue on Angel One's own forum (errorcode AB9019, "No Data
    Available") that hits correctly-formatted requests for many users,
    seemingly independent of anything the caller controls. get_option_chain()
    below treats a failure here as non-fatal for exactly that reason --
    delta/gamma/theta/vega/IV just come back blank rather than the whole
    chain failing, since LTP (the other, more reliable endpoint) is what
    strategy pricing actually depends on."""
    data = _post(GREEK_URL, {"name": "NIFTY", "expirydate": expiry})
    if not data.get("status"):
        raise RuntimeError(f"optionGreek call failed: {data.get('message')}. Raw: {json.dumps(data)[:800]}")
    return _expect(data.get("data"), list, "optionGreek: data['data']", data)


def get_ltp_for_tokens(exchange, tokens):
    """tokens: list of token strings. Returns {token: ltp}. Chunked
    defensively since Angel One caps tokens per quote request."""
    result = {}
    for i in range(0, len(tokens), 50):
        chunk = tokens[i:i + 50]
        data = _post(QUOTE_URL, {"mode": "LTP", "exchangeTokens": {exchange: chunk}})
        body = _expect(data.get("data"), dict, "chain quote: data['data']", data)
        fetched = _expect(body.get("fetched"), list, "chain quote: data['data']['fetched']", data)
        for row in fetched:
            result[row["symbolToken"]] = float(row["ltp"])
    return result


def get_option_chain(expiry):
    """Merged chain: {strike: {'CE': {...}, 'PE': {...}}} with LTP always,
    Greeks/IV when available. See get_greeks()'s docstring for why that
    part is allowed to fail without taking the whole chain down with it."""
    chain_tokens = instruments.get_chain_tokens(expiry)
    if not chain_tokens:
        raise RuntimeError(
            f"No NIFTY option contracts found in the instrument master for expiry '{expiry}'. "
            f"Check the expiry string format matches the scrip master's (e.g. '25APR2024')."
        )

    try:
        greeks = get_greeks(expiry)
    except Exception as e:
        print(f"[market_data] optionGreek unavailable for {expiry}, continuing with LTP only: {e}")
        greeks = []
    greek_lookup = {(float(g["strikePrice"]), g["optionType"]): g for g in greeks}

    all_tokens = [leg["token"] for strikes in chain_tokens.values() for leg in strikes.values()]
    ltps = get_ltp_for_tokens("NFO", all_tokens)

    chain = {}
    for strike, legs in sorted(chain_tokens.items()):
        chain[strike] = {}
        for opt_type, leg in legs.items():
            g = greek_lookup.get((strike, opt_type), {})
            chain[strike][opt_type] = {
                "token": leg["token"],
                "symbol": leg["symbol"],
                "ltp": ltps.get(leg["token"]),
                "delta": g.get("delta"),
                "gamma": g.get("gamma"),
                "theta": g.get("theta"),
                "vega": g.get("vega"),
                "iv": g.get("impliedVolatility"),
                "volume": g.get("tradeVolume"),
            }
    return chain
