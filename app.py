"""
Flask backend for the NIFTY options strategy advisor.
Local dev: python app.py, then open http://localhost:5000
Production (Render etc.): gunicorn app:app -- see Procfile.
"""
import os
import traceback

from flask import Flask, Response, jsonify, request, send_from_directory

import angel_auth
import instruments
import market_data
import strategies
import strategy_engine
from compute import compute_strategy

app = Flask(__name__, static_folder="static", static_url_path="")

# ---- App-level password gate ----
# Separate from your Angel One login -- this is a lock on the whole app,
# since anyone who reaches it and clicks Connect would be using YOUR
# broker session. Only active if APP_USERNAME/APP_PASSWORD are set (so
# local dev on localhost doesn't require it), but treat setting these as
# mandatory before deploying anywhere reachable from the internet.
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")


def _auth_required():
    return Response(
        "Login required.", 401,
        {"WWW-Authenticate": 'Basic realm="Options Strategy Advisor"'},
    )


@app.before_request
def _check_app_password():
    if not APP_USERNAME or not APP_PASSWORD:
        return  # gate disabled -- no credentials configured (local dev default)
    auth = request.authorization
    if not auth or auth.username != APP_USERNAME or auth.password != APP_PASSWORD:
        return _auth_required()


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---- Connection status / login gate ----

@app.route("/api/status")
def status():
    """Cheap check -- does NOT attempt a login, just reports whether one
    already happened this process. The frontend gates the rest of the UI
    on this before showing the tool."""
    return jsonify({
        "connected": angel_auth.is_connected(),
        "client_code": angel_auth.connected_client_code(),
    })


@app.route("/api/login", methods=["POST"])
def login():
    """Explicit login, triggered by the Connect button rather than
    happening silently on the first data call."""
    try:
        session = angel_auth.login()
        return jsonify({"connected": True, "client_code": session["client_code"]})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"connected": False, "error": str(e)}), 500


@app.route("/api/vix")
def vix():
    try:
        v = market_data.get_vix()
        return jsonify({"vix": v, "iv_regime": strategy_engine.classify_iv_regime(v)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/expiries")
def expiries():
    try:
        return jsonify(instruments.get_expiries())
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies")
def strategies_list():
    """Full catalog for the 'browse all strategies' picker."""
    return jsonify(strategies.list_catalog())


@app.route("/api/optionchain")
def option_chain():
    expiry = request.args.get("expiry")
    if not expiry:
        return jsonify({"error": "expiry is required"}), 400
    try:
        spot = market_data.get_spot_price()
        chain = market_data.get_option_chain(expiry)
        return jsonify({"spot": spot, "expiry": expiry, "chain": chain})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/suggest")
def suggest():
    """Guided mode: predicted direction (+ risk preference) -> one of 9
    core strategies. IV regime is no longer a manual dropdown -- it's
    classified live from India VIX (see strategy_engine.classify_iv_regime)."""
    expiry = request.args.get("expiry")
    direction = request.args.get("direction")
    risk_pref = request.args.get("risk_pref")

    if not all([expiry, direction, risk_pref]):
        return jsonify({"error": "expiry, direction, risk_pref are all required"}), 400

    try:
        vix = market_data.get_vix()
        iv_regime = strategy_engine.classify_iv_regime(vix)
        key = strategy_engine.pick_strategy(direction, iv_regime, risk_pref)
        return jsonify(compute_strategy(key, expiry, vix=vix, iv_regime=iv_regime))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy")
def strategy_lookup():
    """Browse mode: any catalog key, picked directly by the user."""
    key = request.args.get("key")
    expiry = request.args.get("expiry")
    if not key or not expiry:
        return jsonify({"error": "key and expiry are required"}), 400
    try:
        vix, iv_regime = None, None
        try:
            vix = market_data.get_vix()
            iv_regime = strategy_engine.classify_iv_regime(vix)
        except Exception:
            pass  # VIX display is informational in browse mode, not required to show the strategy
        return jsonify(compute_strategy(key, expiry, vix=vix, iv_regime=iv_regime))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # This block only runs for local dev (`python app.py`). In production,
    # gunicorn imports the `app` object directly via the Procfile and never
    # executes this -- so debug mode (and its interactive debugger, a real
    # code-execution risk if ever exposed) never runs outside your machine.
    app.run(debug=True, port=5000)
