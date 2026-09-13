"""
Orchestrates one strategy's full computation: fetches whatever live
data that strategy needs (spot, chain, futures, a second expiry for
calendar/diagonal spreads), builds concrete legs, and runs the
payoff/breakeven math.

Framework-agnostic on purpose -- both app.py (Flask) and streamlit_app.py
import this, so a fix here (like the float/int strike key bug) only
needs to happen once instead of drifting between two copies.
"""
import instruments
import market_data
import strategies
import strategy_engine


def compute_strategy(key, expiry, vix=None, iv_regime=None):
    if key not in strategies.CATALOG:
        raise ValueError(f"Unknown strategy key: {key}")
    entry = strategies.CATALOG[key]
    needs_fut = any(l["instr"] == "FUT" for l in entry["legs"])
    needs_back = entry.get("multi_expiry", False)

    spot = market_data.get_spot_price()
    chain_front = market_data.get_option_chain(expiry)

    back_expiry, chain_back, days_between = None, None, None
    if needs_back:
        back_expiry = instruments.get_next_expiry(expiry)
        if back_expiry is None:
            raise RuntimeError(
                f"No expiry listed after {expiry} to use as the far leg -- "
                f"pick an earlier front expiry for a calendar/diagonal spread."
            )
        chain_back = market_data.get_option_chain(back_expiry)
        days_between = strategy_engine.days_between_expiries(expiry, back_expiry)

    fut_price, fut_symbol = None, None
    if needs_fut:
        fut_price, fut_info = market_data.get_futures_price()
        fut_symbol = fut_info["symbol"]

    legs = strategy_engine.build_legs_from_catalog(
        key, spot, chain_front, chain_back=chain_back,
        fut_price=fut_price, fut_symbol=fut_symbol, days_between=days_between,
    )
    premium = strategy_engine.net_premium(legs)
    max_p, max_l = strategy_engine.max_profit_loss(legs, spot)
    bes = strategy_engine.breakevens(legs, spot)
    curve = strategy_engine.payoff_curve(legs, spot)

    return {
        "spot": spot,
        "vix": vix,
        "iv_regime": iv_regime,
        "expiry": expiry,
        "back_expiry": back_expiry,
        "futures_price": fut_price,
        "futures_symbol": fut_symbol,
        "strategy": key,
        "strategy_name": entry["name"],
        "description": entry["description"],
        "multi_expiry": needs_back,
        "legs": legs,
        "net_premium": premium,
        "net_premium_type": "credit" if premium > 0 else "debit",
        "max_profit": max_p,
        "max_loss": max_l,
        "breakevens": bes,
        "payoff_curve": curve,
        "chain": chain_front,
    }
