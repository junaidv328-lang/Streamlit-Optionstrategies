import os
from dotenv import load_dotenv

load_dotenv()

ANGEL_API_KEY = os.getenv("ANGEL_API_KEY")
ANGEL_CLIENT_CODE = os.getenv("ANGEL_CLIENT_CODE")
ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")

BASE_URL = "https://apiconnect.angelone.in"  # migrated from apiconnect.angelbroking.com

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SCRIP_MASTER_CACHE = "instrument_cache.json"
SCRIP_MASTER_MAX_AGE_HOURS = 24

# NIFTY 50 index -- same token used in the chart pattern app's quick-pick dropdown
NIFTY_SPOT_TOKEN = "99926000"
NIFTY_SPOT_EXCHANGE = "NSE"

# India VIX -- confirmed from Angel One's own SmartAPI announcement
# (tradingSymbol "India VIX", symbolToken "99926017", exchange NSE)
VIX_TOKEN = "99926017"
VIX_EXCHANGE = "NSE"

# Single cut for classifying live VIX into the two IV-regime buckets the
# guided rule table uses. India VIX has roughly run ~11-15 in calm periods
# and spiked well above 20 in stress over recent years, so 15 is a
# reasonable starting line -- but it's a static number, not something
# derived from current data. Adjust it if it doesn't match what you'd
# actually call "high" IV right now.
VIX_LOW_HIGH_CUTOFF = 15.0

NIFTY_STRIKE_STEP = 50

# Used only for the Black-Scholes estimate of a still-alive back-month
# leg's value in calendar/diagonal payoff diagrams -- rough approximation
# of the risk-free rate, not fetched live.
RISK_FREE_RATE = 0.065


def require_config():
    missing = [name for name, val in {
        "ANGEL_API_KEY": ANGEL_API_KEY,
        "ANGEL_CLIENT_CODE": ANGEL_CLIENT_CODE,
        "ANGEL_PASSWORD": ANGEL_PASSWORD,
        "ANGEL_TOTP_SECRET": ANGEL_TOTP_SECRET,
    }.items() if not val]
    if missing:
        raise RuntimeError(
            f"Missing .env values: {', '.join(missing)}. "
            f"Copy .env.template to .env and fill it in."
        )
