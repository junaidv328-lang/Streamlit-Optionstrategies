"""
Strategy selection (guided mode) and the generic leg-builder / payoff
math that powers every strategy in strategies.CATALOG.

Guided mode (pick_strategy) is a small, deliberately conservative rule
table -- 3 inputs mapped to 9 well-established strategies. The full
~58-strategy catalog is meant to be browsed and picked directly (see
build_legs_from_catalog), not auto-selected, since 3 inputs aren't
enough signal to safely choose between e.g. a butterfly and a ladder.
"""
import math
import time

import config
import strategies

STRIKE_STEP = config.NIFTY_STRIKE_STEP


def nearest_strike(spot, step=STRIKE_STEP):
    return round(spot / step) * step


# ---- Guided mode: (direction, iv_regime, risk_pref) -> catalog key ----
RULES = {
    ("bullish", "low", "defined"): "bull_call_spread",
    ("bullish", "high", "defined"): "bull_put_spread",
    ("bullish", "low", "undefined"): "long_call",
    ("bullish", "high", "undefined"): "long_call",
    ("bearish", "low", "defined"): "bear_put_spread",
    ("bearish", "high", "defined"): "bear_call_spread",
    ("bearish", "low", "undefined"): "long_put",
    ("bearish", "high", "undefined"): "long_put",
    ("neutral", "low", "defined"): "long_straddle",
    ("neutral", "low", "undefined"): "long_straddle",
    ("neutral", "high", "defined"): "iron_condor",
    ("neutral", "high", "undefined"): "short_strangle",
}


def pick_strategy(direction, iv_regime, risk_pref):
    key = RULES.get((direction, iv_regime, risk_pref))
    if key is None:
        raise ValueError(f"No rule for direction={direction}, iv_regime={iv_regime}, risk_pref={risk_pref}")
    return key


def classify_iv_regime(vix):
    """Live VIX -> 'low' or 'high', the two buckets the rule table above
    uses. See config.VIX_LOW_HIGH_CUTOFF for the cutoff and its caveat --
    it's a static line, not something derived from current data."""
    return "low" if vix < config.VIX_LOW_HIGH_CUTOFF else "high"


def days_between_expiries(front_expiry, back_expiry):
    """Calendar days between two Angel One expiry strings, e.g. '25APR2024'."""
    t1 = time.strptime(front_expiry, "%d%b%Y")
    t2 = time.strptime(back_expiry, "%d%b%Y")
    return abs(int(time.mktime(t2) - time.mktime(t1)) // 86400)


# ---- Generic leg construction from a strategies.CATALOG entry ----

def build_legs_from_catalog(key, spot, chain_front, chain_back=None,
                             fut_price=None, fut_symbol=None, days_between=None):
    """Turns a declarative catalog entry into concrete legs with live
    strikes, symbols and premiums:
    [{'action', 'instr', 'strike', 'qty', 'ltp', 'symbol', 'expiry_role', 'iv', 'T_days'}, ...]
    """
    entry = strategies.CATALOG[key]
    atm = nearest_strike(spot)
    legs = []
    for tmpl in entry["legs"]:
        instr = tmpl["instr"]
        action = tmpl["action"]
        qty = tmpl.get("qty", 1)
        role = tmpl.get("expiry", "front")

        if instr == "FUT":
            legs.append({
                "action": action, "instr": "FUT", "strike": None, "qty": qty,
                "ltp": fut_price, "symbol": fut_symbol, "expiry_role": "front",
                "iv": None, "T_days": None,
            })
            continue

        strike = atm + tmpl["offset"] * STRIKE_STEP
        chain = chain_front if role == "front" else chain_back
        row = (chain or {}).get(strike, {}).get(instr, {})

        leg = {
            "action": action, "instr": instr, "strike": strike, "qty": qty,
            "ltp": row.get("ltp"), "symbol": row.get("symbol"), "expiry_role": role,
        }
        if role == "back":
            iv = row.get("iv")
            leg["iv"] = (iv / 100) if iv else None
            leg["T_days"] = days_between
        else:
            leg["iv"] = None
            leg["T_days"] = None
        legs.append(leg)
    return legs


# ---- Payoff math ----

def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bs_price(S, K, T_years, r, sigma, instr):
    """Black-Scholes value of a still-alive option -- used only to
    estimate a back-month leg's remaining value at the front expiry
    date in calendar/diagonal payoff diagrams. Holds today's IV
    constant, which is an approximation, not a forecast."""
    if T_years <= 0 or not sigma or sigma <= 0:
        return max(0, S - K) if instr == "CE" else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T_years) / (sigma * math.sqrt(T_years))
    d2 = d1 - sigma * math.sqrt(T_years)
    if instr == "CE":
        return S * _norm_cdf(d1) - K * math.exp(-r * T_years) * _norm_cdf(d2)
    return K * math.exp(-r * T_years) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _leg_entry_cashflow(leg):
    """Cashflow when opening this leg: negative to buy, positive to sell.
    Futures legs carry no premium (margin isn't modeled here)."""
    if leg["instr"] == "FUT":
        return 0
    ltp = leg["ltp"] or 0
    sign = -1 if leg["action"] == "BUY" else 1
    return sign * leg["qty"] * ltp


def net_premium(legs):
    """Positive = net credit received on entry, negative = net debit paid."""
    return sum(_leg_entry_cashflow(l) for l in legs)


def payoff_at(legs, price, r=config.RISK_FREE_RATE):
    """P/L if underlying is at `price`, valued at the front expiry.
    Front-expiry option legs use intrinsic value (they've expired).
    Back-expiry legs (calendar/diagonal) are still alive, so they're
    valued with Black-Scholes instead. Futures legs are linear."""
    total = net_premium(legs)
    for l in legs:
        sign = 1 if l["action"] == "BUY" else -1
        if l["instr"] == "FUT":
            entry = l["ltp"] or 0
            total += sign * l["qty"] * (price - entry)
        elif l["expiry_role"] == "front":
            intrinsic = max(0, price - l["strike"]) if l["instr"] == "CE" else max(0, l["strike"] - price)
            total += sign * l["qty"] * intrinsic
        else:
            val = _bs_price(price, l["strike"], (l["T_days"] or 0) / 365, r, l["iv"], l["instr"])
            total += sign * l["qty"] * val
    return total


def breakevens(legs, spot, scan_range=2000, step=1):
    """Scans a price range for payoff sign changes -- robust across all
    strategy shapes rather than solving each one analytically."""
    lo, hi = int(spot - scan_range), int(spot + scan_range)
    points = []
    prev_payoff = None
    for price in range(lo, hi, step):
        p = payoff_at(legs, price)
        if prev_payoff is not None and (prev_payoff <= 0 < p or prev_payoff > 0 >= p):
            points.append(price)
        prev_payoff = p
    return points


def max_profit_loss(legs, spot, scan_range=2000, step=5):
    lo, hi = int(spot - scan_range), int(spot + scan_range)
    payoffs = [payoff_at(legs, price) for price in range(lo, hi, step)]
    return max(payoffs), min(payoffs)


def payoff_curve(legs, spot, scan_range=2000, step=10):
    """[[price, payoff], ...] -- computed once here (single source of
    truth, including the Black-Scholes path for calendar/diagonal legs)
    so the frontend only has to plot it, not reimplement the math."""
    lo, hi = int(spot - scan_range), int(spot + scan_range)
    return [[price, round(payoff_at(legs, price), 2)] for price in range(lo, hi, step)]
