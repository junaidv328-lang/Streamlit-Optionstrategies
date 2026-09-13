"""
Angel One SmartAPI login/session handling.

If you already have a working auth module from your other SmartAPI
projects (ScalpEdge, the chart pattern app, etc.), it's a straight
swap-in here -- the rest of this app only calls get_session() and
auth_headers(), so as long as those return the same shape it doesn't
matter which login implementation sits underneath.

NOTE: Angel One's JWT session tokens expire after a few hours. If
calls start failing with an auth error mid-session, call login()
again rather than reusing the cached session indefinitely.
"""
import pyotp
from SmartApi import SmartConnect

import config

_session_cache = {"session": None}


def login():
    config.require_config()
    totp = pyotp.TOTP(config.ANGEL_TOTP_SECRET).now()
    smart = SmartConnect(api_key=config.ANGEL_API_KEY)
    data = smart.generateSession(config.ANGEL_CLIENT_CODE, config.ANGEL_PASSWORD, totp)

    if not data.get("status"):
        raise RuntimeError(f"Angel One login failed: {data.get('message')}")

    jwt_token = data["data"]["jwtToken"]
    if jwt_token.lower().startswith("bearer "):
        jwt_token = jwt_token[7:]  # some accounts get it back pre-prefixed -- avoid "Bearer Bearer <token>"

    session = {
        "smart": smart,
        "jwt_token": jwt_token,
        "refresh_token": data["data"]["refreshToken"],
        "feed_token": smart.getfeedToken(),
        "client_code": config.ANGEL_CLIENT_CODE,
    }
    _session_cache["session"] = session
    return session


def get_session():
    """Returns the cached session, logging in if there isn't one yet."""
    if _session_cache["session"] is None:
        return login()
    return _session_cache["session"]


def refresh():
    """Force a fresh login -- call this if a request fails on auth."""
    _session_cache["session"] = None
    return get_session()


def is_connected():
    return _session_cache["session"] is not None


def connected_client_code():
    session = _session_cache["session"]
    return session["client_code"] if session else None


def auth_headers(session):
    return {
        "Authorization": f"Bearer {session['jwt_token']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": "00:00:00:00:00:00",
        "X-PrivateKey": config.ANGEL_API_KEY,
    }
