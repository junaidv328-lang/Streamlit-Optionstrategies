"""
Full options strategy catalog -- standard, industry-wide strategy
definitions and names (covered call, iron condor, seagull spread,
etc. are generic terminology used across every options textbook and
broker platform, not specific to any single source).

Each entry is a declarative leg template so strategy_engine.py can
build concrete strikes/quantities generically instead of one
hand-written function per strategy:

    leg template = {
        'instr':  'CE' | 'PE' | 'FUT'
        'action': 'BUY' | 'SELL'
        'offset': int   -- strike steps from ATM (0 = ATM); ignored for FUT
        'qty':    int   -- contract multiplier, default 1 (for ratio/backspreads/butterflies)
        'expiry': 'front' | 'back'  -- 'back' = next listed expiry after the
                                        one you picked (calendar/diagonal only)
    }

FUT legs use the front-month NIFTY future as a stand-in for "the
underlying" -- there's no NIFTY stock to hold directly, so covered/
protective/synthetic strategies here are built against the future.

W  = one near strike step out (100 points on NIFTY, i.e. 2 x 50pt strikes)
W2 = two steps out (200 points)
"""

W, W2 = 2, 4


def _leg(instr, action, offset=0, qty=1, expiry="front"):
    return {"instr": instr, "action": action, "offset": offset, "qty": qty, "expiry": expiry}


CATALOG = {
    # ---- Directional (single leg) ----
    "long_call": {
        "name": "Long Call", "category": "Directional",
        "description": "Buy a call. Simple bullish bet: unlimited upside, risk capped at the premium paid.",
        "legs": [_leg("CE", "BUY", 0)],
    },
    "long_put": {
        "name": "Long Put", "category": "Directional",
        "description": "Buy a put. Simple bearish bet: large downside payoff, risk capped at the premium paid.",
        "legs": [_leg("PE", "BUY", 0)],
    },

    # ---- Covered & Protective (option + futures as the underlying) ----
    "covered_call": {
        "name": "Covered Call", "category": "Covered & Protective",
        "description": "Long futures + sell an OTM call against it. Collects premium, caps upside at the short strike.",
        "legs": [_leg("FUT", "BUY"), _leg("CE", "SELL", W)],
    },
    "covered_put": {
        "name": "Covered Put", "category": "Covered & Protective",
        "description": "Short futures + sell an OTM put against it. Collects premium, caps downside gain at the short strike.",
        "legs": [_leg("FUT", "SELL"), _leg("PE", "SELL", -W)],
    },
    "protective_put": {
        "name": "Protective Put", "category": "Covered & Protective",
        "description": "Long futures + buy a put as insurance. Caps downside, keeps upside minus the premium paid.",
        "legs": [_leg("FUT", "BUY"), _leg("PE", "BUY", 0)],
    },
    "protective_call": {
        "name": "Protective Call", "category": "Covered & Protective",
        "description": "Short futures + buy a call as insurance. Caps the risk on a short futures position.",
        "legs": [_leg("FUT", "SELL"), _leg("CE", "BUY", 0)],
    },
    "collar": {
        "name": "Collar", "category": "Covered & Protective",
        "description": "Long futures + protective put + covered call. Cheap (often near-zero cost) downside protection, upside capped.",
        "legs": [_leg("FUT", "BUY"), _leg("PE", "BUY", -W), _leg("CE", "SELL", W)],
    },

    # ---- Vertical Spreads ----
    "bull_call_spread": {
        "name": "Bull Call Spread", "category": "Vertical Spreads",
        "description": "Buy an ATM call, sell a further OTM call. Caps both cost and profit; cheaper than a naked call.",
        "legs": [_leg("CE", "BUY", 0), _leg("CE", "SELL", W)],
    },
    "bear_put_spread": {
        "name": "Bear Put Spread", "category": "Vertical Spreads",
        "description": "Buy an ATM put, sell a further OTM put. Caps both cost and profit; cheaper than a naked put.",
        "legs": [_leg("PE", "BUY", 0), _leg("PE", "SELL", -W)],
    },
    "bull_put_spread": {
        "name": "Bull Put Spread", "category": "Vertical Spreads",
        "description": "Sell an OTM put, buy a further OTM put for protection. Net credit; profits if price stays above the short strike.",
        "legs": [_leg("PE", "SELL", -W), _leg("PE", "BUY", -W2)],
    },
    "bear_call_spread": {
        "name": "Bear Call Spread", "category": "Vertical Spreads",
        "description": "Sell an OTM call, buy a further OTM call for protection. Net credit; profits if price stays below the short strike.",
        "legs": [_leg("CE", "SELL", W), _leg("CE", "BUY", W2)],
    },

    # ---- Synthetic Positions ----
    "long_synthetic_forward": {
        "name": "Long Synthetic Forward", "category": "Synthetic Positions",
        "description": "Buy an ATM call, sell an ATM put. Mimics a long futures position using options.",
        "legs": [_leg("CE", "BUY", 0), _leg("PE", "SELL", 0)],
    },
    "short_synthetic_forward": {
        "name": "Short Synthetic Forward", "category": "Synthetic Positions",
        "description": "Sell an ATM call, buy an ATM put. Mimics a short futures position using options.",
        "legs": [_leg("CE", "SELL", 0), _leg("PE", "BUY", 0)],
    },
    "long_combo": {
        "name": "Long Combo", "category": "Synthetic Positions",
        "description": "Buy an OTM call, sell an OTM put. Bullish, cheaper than a synthetic forward, with a small gap around ATM.",
        "legs": [_leg("CE", "BUY", W), _leg("PE", "SELL", -W)],
    },
    "short_combo": {
        "name": "Short Combo", "category": "Synthetic Positions",
        "description": "Sell an OTM call, buy an OTM put. Bearish mirror of the long combo.",
        "legs": [_leg("CE", "SELL", W), _leg("PE", "BUY", -W)],
    },

    # ---- Ladders ----
    "bull_call_ladder": {
        "name": "Bull Call Ladder", "category": "Ladders",
        "description": "Bull call spread plus an extra short call further out. Reduces cost vs. a plain spread but opens uncapped risk if price runs far above the top strike.",
        "legs": [_leg("CE", "BUY", 0), _leg("CE", "SELL", W), _leg("CE", "SELL", W2)],
    },
    "bull_put_ladder": {
        "name": "Bull Put Ladder", "category": "Ladders",
        "description": "Bull put spread plus an extra long put further out. Turns a credit spread into a position with defined (and larger) downside coverage, at extra cost.",
        "legs": [_leg("PE", "SELL", -W), _leg("PE", "BUY", -W2), _leg("PE", "BUY", -2 * W2)],
    },
    "bear_call_ladder": {
        "name": "Bear Call Ladder", "category": "Ladders",
        "description": "Bear call spread plus an extra long call further out. Adds upside coverage to a credit spread, at extra cost.",
        "legs": [_leg("CE", "SELL", W), _leg("CE", "BUY", W2), _leg("CE", "BUY", 2 * W2)],
    },
    "bear_put_ladder": {
        "name": "Bear Put Ladder", "category": "Ladders",
        "description": "Bear put spread plus an extra short put further out. Reduces cost vs. a plain spread but opens uncapped risk if price falls far below the bottom strike.",
        "legs": [_leg("PE", "BUY", 0), _leg("PE", "SELL", -W), _leg("PE", "SELL", -W2)],
    },

    # ---- Calendar & Diagonal (two expiries) ----
    "calendar_call_spread": {
        "name": "Calendar Call Spread", "category": "Calendar & Diagonal",
        "description": "Sell a near-expiry ATM call, buy the same strike in the next expiry. Profits from time decay on the short leg; needs price to stay near the strike.",
        "legs": [_leg("CE", "SELL", 0, expiry="front"), _leg("CE", "BUY", 0, expiry="back")],
        "multi_expiry": True,
    },
    "calendar_put_spread": {
        "name": "Calendar Put Spread", "category": "Calendar & Diagonal",
        "description": "Sell a near-expiry ATM put, buy the same strike in the next expiry. Same idea as a calendar call spread, built with puts.",
        "legs": [_leg("PE", "SELL", 0, expiry="front"), _leg("PE", "BUY", 0, expiry="back")],
        "multi_expiry": True,
    },
    "diagonal_call_spread": {
        "name": "Diagonal Call Spread", "category": "Calendar & Diagonal",
        "description": "Sell a near-expiry OTM call, buy an ATM call in the next expiry. Calendar spread with a directional (bullish) tilt from the strike offset.",
        "legs": [_leg("CE", "SELL", W, expiry="front"), _leg("CE", "BUY", 0, expiry="back")],
        "multi_expiry": True,
    },
    "diagonal_put_spread": {
        "name": "Diagonal Put Spread", "category": "Calendar & Diagonal",
        "description": "Sell a near-expiry OTM put, buy an ATM put in the next expiry. Calendar spread with a directional (bearish) tilt from the strike offset.",
        "legs": [_leg("PE", "SELL", -W, expiry="front"), _leg("PE", "BUY", 0, expiry="back")],
        "multi_expiry": True,
    },

    # ---- Straddles, Strangles & Guts ----
    "long_straddle": {
        "name": "Long Straddle", "category": "Straddles, Strangles & Guts",
        "description": "Buy an ATM call and an ATM put. Profits from a big move either direction; needs the move to outrun time decay.",
        "legs": [_leg("CE", "BUY", 0), _leg("PE", "BUY", 0)],
    },
    "long_strangle": {
        "name": "Long Strangle", "category": "Straddles, Strangles & Guts",
        "description": "Buy an OTM call and an OTM put. Cheaper than a straddle, but needs a bigger move to profit.",
        "legs": [_leg("CE", "BUY", W), _leg("PE", "BUY", -W)],
    },
    "long_guts": {
        "name": "Long Guts", "category": "Straddles, Strangles & Guts",
        "description": "Buy an ITM call and an ITM put. Straddle-like payoff shape, built with in-the-money strikes -- more expensive, more intrinsic value up front.",
        "legs": [_leg("CE", "BUY", -W), _leg("PE", "BUY", W)],
    },
    "short_straddle": {
        "name": "Short Straddle", "category": "Straddles, Strangles & Guts",
        "description": "Sell an ATM call and an ATM put. Profits if price stays near the strike; uncapped risk if it doesn't.",
        "legs": [_leg("CE", "SELL", 0), _leg("PE", "SELL", 0)],
    },
    "short_strangle": {
        "name": "Short Strangle", "category": "Straddles, Strangles & Guts",
        "description": "Sell an OTM call and an OTM put. Profits if price stays in a range; loss is uncapped if it breaks out.",
        "legs": [_leg("CE", "SELL", W), _leg("PE", "SELL", -W)],
    },
    "short_guts": {
        "name": "Short Guts", "category": "Straddles, Strangles & Guts",
        "description": "Sell an ITM call and an ITM put. Collects more premium up front than a short strangle, with a narrower profit zone.",
        "legs": [_leg("CE", "SELL", -W), _leg("PE", "SELL", W)],
    },

    # ---- Synthetic Straddles (options + futures) ----
    "long_call_synthetic_straddle": {
        "name": "Long Call Synthetic Straddle", "category": "Synthetic Straddles",
        "description": "Buy two ATM calls, sell one futures. Recreates a long straddle's payoff shape using only calls plus a short future.",
        "legs": [_leg("CE", "BUY", 0, qty=2), _leg("FUT", "SELL")],
    },
    "long_put_synthetic_straddle": {
        "name": "Long Put Synthetic Straddle", "category": "Synthetic Straddles",
        "description": "Buy two ATM puts, buy one futures. Recreates a long straddle's payoff shape using only puts plus a long future.",
        "legs": [_leg("PE", "BUY", 0, qty=2), _leg("FUT", "BUY")],
    },
    "short_call_synthetic_straddle": {
        "name": "Short Call Synthetic Straddle", "category": "Synthetic Straddles",
        "description": "Sell two ATM calls, buy one futures. Recreates a short straddle's payoff shape using only calls plus a long future.",
        "legs": [_leg("CE", "SELL", 0, qty=2), _leg("FUT", "BUY")],
    },
    "short_put_synthetic_straddle": {
        "name": "Short Put Synthetic Straddle", "category": "Synthetic Straddles",
        "description": "Sell two ATM puts, sell one futures. Recreates a short straddle's payoff shape using only puts plus a short future.",
        "legs": [_leg("PE", "SELL", 0, qty=2), _leg("FUT", "SELL")],
    },
    "covered_short_straddle": {
        "name": "Covered Short Straddle", "category": "Synthetic Straddles",
        "description": "Short straddle plus a long futures position covering the short call side. Reduces the uncapped upside risk of a plain short straddle.",
        "legs": [_leg("CE", "SELL", 0), _leg("PE", "SELL", 0), _leg("FUT", "BUY")],
    },
    "covered_short_strangle": {
        "name": "Covered Short Strangle", "category": "Synthetic Straddles",
        "description": "Short strangle plus a long futures position covering the short call side. Reduces the uncapped upside risk of a plain short strangle.",
        "legs": [_leg("CE", "SELL", W), _leg("PE", "SELL", -W), _leg("FUT", "BUY")],
    },

    # ---- Strap & Strip ----
    "strap": {
        "name": "Strap", "category": "Straddles, Strangles & Guts",
        "description": "Buy two ATM calls and one ATM put. A straddle with a bullish bias -- profits more from an up move than a down move of the same size.",
        "legs": [_leg("CE", "BUY", 0, qty=2), _leg("PE", "BUY", 0)],
    },
    "strip": {
        "name": "Strip", "category": "Straddles, Strangles & Guts",
        "description": "Buy one ATM call and two ATM puts. A straddle with a bearish bias -- profits more from a down move than an up move of the same size.",
        "legs": [_leg("CE", "BUY", 0), _leg("PE", "BUY", 0, qty=2)],
    },

    # ---- Ratio Spreads & Backspreads ----
    "call_ratio_backspread": {
        "name": "Call Ratio Backspread", "category": "Ratio Spreads & Backspreads",
        "description": "Sell one ATM call, buy two further OTM calls. Net long calls -- limited risk, big upside if price runs, small loss zone just above ATM.",
        "legs": [_leg("CE", "SELL", 0), _leg("CE", "BUY", W, qty=2)],
    },
    "put_ratio_backspread": {
        "name": "Put Ratio Backspread", "category": "Ratio Spreads & Backspreads",
        "description": "Sell one ATM put, buy two further OTM puts. Net long puts -- limited risk, big downside payoff, small loss zone just below ATM.",
        "legs": [_leg("PE", "SELL", 0), _leg("PE", "BUY", -W, qty=2)],
    },
    "ratio_call_spread": {
        "name": "Ratio Call Spread", "category": "Ratio Spreads & Backspreads",
        "description": "Buy one ATM call, sell two further OTM calls. Net short calls -- collects more premium than a plain bull call spread, opens uncapped risk far above the short strikes.",
        "legs": [_leg("CE", "BUY", 0), _leg("CE", "SELL", W, qty=2)],
    },
    "ratio_put_spread": {
        "name": "Ratio Put Spread", "category": "Ratio Spreads & Backspreads",
        "description": "Buy one ATM put, sell two further OTM puts. Net short puts -- collects more premium than a plain bear put spread, opens uncapped risk far below the short strikes.",
        "legs": [_leg("PE", "BUY", 0), _leg("PE", "SELL", -W, qty=2)],
    },

    # ---- Butterflies ----
    "long_call_butterfly": {
        "name": "Long Call Butterfly", "category": "Butterflies",
        "description": "Buy 1 ITM call, sell 2 ATM calls, buy 1 OTM call, evenly spaced. Low-cost, defined-risk bet that price finishes near ATM.",
        "legs": [_leg("CE", "BUY", -W), _leg("CE", "SELL", 0, qty=2), _leg("CE", "BUY", W)],
    },
    "modified_call_butterfly": {
        "name": "Modified Call Butterfly", "category": "Butterflies",
        "description": "Long call butterfly with uneven wing widths, skewing the payoff for a directional bias while keeping risk defined.",
        "legs": [_leg("CE", "BUY", -W), _leg("CE", "SELL", 0, qty=2), _leg("CE", "BUY", W2)],
    },
    "long_put_butterfly": {
        "name": "Long Put Butterfly", "category": "Butterflies",
        "description": "Buy 1 OTM put, sell 2 ATM puts, buy 1 ITM put, evenly spaced. Put-built equivalent of a long call butterfly.",
        "legs": [_leg("PE", "BUY", W), _leg("PE", "SELL", 0, qty=2), _leg("PE", "BUY", -W)],
    },
    "modified_put_butterfly": {
        "name": "Modified Put Butterfly", "category": "Butterflies",
        "description": "Long put butterfly with uneven wing widths, skewing the payoff for a directional bias while keeping risk defined.",
        "legs": [_leg("PE", "BUY", W), _leg("PE", "SELL", 0, qty=2), _leg("PE", "BUY", -W2)],
    },
    "short_call_butterfly": {
        "name": "Short Call Butterfly", "category": "Butterflies",
        "description": "Mirror of the long call butterfly (sell the wings, buy the body). Small, defined profit if price makes a big move away from ATM.",
        "legs": [_leg("CE", "SELL", -W), _leg("CE", "BUY", 0, qty=2), _leg("CE", "SELL", W)],
    },
    "short_put_butterfly": {
        "name": "Short Put Butterfly", "category": "Butterflies",
        "description": "Mirror of the long put butterfly (sell the wings, buy the body). Small, defined profit if price makes a big move away from ATM.",
        "legs": [_leg("PE", "SELL", W), _leg("PE", "BUY", 0, qty=2), _leg("PE", "SELL", -W)],
    },
    "long_iron_butterfly": {
        "name": "\u201cLong\u201d Iron Butterfly", "category": "Butterflies",
        "description": "Sell an ATM call and put, buy further OTM call and put as wings. Net credit, defined risk, profits if price stays near ATM -- the common 'iron butterfly'.",
        "legs": [_leg("CE", "SELL", 0), _leg("PE", "SELL", 0), _leg("CE", "BUY", W), _leg("PE", "BUY", -W)],
    },
    "short_iron_butterfly": {
        "name": "\u201cShort\u201d Iron Butterfly", "category": "Butterflies",
        "description": "Buy an ATM call and put, sell further OTM call and put as wings. Net debit, defined risk, profits from a big move away from ATM -- the reverse iron butterfly.",
        "legs": [_leg("CE", "BUY", 0), _leg("PE", "BUY", 0), _leg("CE", "SELL", W), _leg("PE", "SELL", -W)],
    },

    # ---- Condors ----
    "long_call_condor": {
        "name": "Long Call Condor", "category": "Condors",
        "description": "Buy a low-strike call, sell two middle-strike calls, buy a high-strike call -- all calls, four strikes. Wider, cheaper cousin of a call butterfly.",
        "legs": [_leg("CE", "BUY", -W2), _leg("CE", "SELL", -W), _leg("CE", "SELL", W), _leg("CE", "BUY", W2)],
    },
    "long_put_condor": {
        "name": "Long Put Condor", "category": "Condors",
        "description": "Buy a high-strike put, sell two middle-strike puts, buy a low-strike put -- all puts, four strikes. Put-built equivalent of a long call condor.",
        "legs": [_leg("PE", "BUY", W2), _leg("PE", "SELL", W), _leg("PE", "SELL", -W), _leg("PE", "BUY", -W2)],
    },
    "short_call_condor": {
        "name": "Short Call Condor", "category": "Condors",
        "description": "Mirror of the long call condor (sell the wings, buy the middle). Profits from a big move away from the middle strikes.",
        "legs": [_leg("CE", "SELL", -W2), _leg("CE", "BUY", -W), _leg("CE", "BUY", W), _leg("CE", "SELL", W2)],
    },
    "short_put_condor": {
        "name": "Short Put Condor", "category": "Condors",
        "description": "Mirror of the long put condor (sell the wings, buy the middle). Profits from a big move away from the middle strikes.",
        "legs": [_leg("PE", "SELL", W2), _leg("PE", "BUY", W), _leg("PE", "BUY", -W), _leg("PE", "SELL", -W2)],
    },
    "long_iron_condor": {
        "name": "Long Iron Condor", "category": "Condors",
        "description": "Sell an OTM call and put, buy further OTM call and put as protection. Net credit, defined risk, profits if price stays in the middle range -- the common 'iron condor'.",
        "legs": [_leg("CE", "SELL", W), _leg("CE", "BUY", W2), _leg("PE", "SELL", -W), _leg("PE", "BUY", -W2)],
    },
    "short_iron_condor": {
        "name": "Short Iron Condor", "category": "Condors",
        "description": "Buy an OTM call and put, sell further OTM call and put. Net debit, defined risk, profits if price moves outside the range -- the reverse iron condor.",
        "legs": [_leg("CE", "BUY", W), _leg("CE", "SELL", W2), _leg("PE", "BUY", -W), _leg("PE", "SELL", -W2)],
    },

    # ---- Other Combinations ----
    "long_box": {
        "name": "Long Box", "category": "Other Combinations",
        "description": "Bull call spread + bear put spread at the same two strikes. Locks in a fixed payoff (the strike width) regardless of where price ends up -- an arbitrage/financing structure, not a market bet.",
        "legs": [_leg("CE", "BUY", 0), _leg("CE", "SELL", W), _leg("PE", "SELL", 0), _leg("PE", "BUY", W)],
    },
    "bullish_long_seagull_spread": {
        "name": "Bullish Long Seagull Spread", "category": "Other Combinations",
        "description": "Sell an OTM put to help finance a bull call spread. Bullish, low net cost, but carries assignment risk on the short put if price falls hard.",
        "legs": [_leg("PE", "SELL", -W), _leg("CE", "BUY", 0), _leg("CE", "SELL", W2)],
    },
    "bullish_short_seagull_spread": {
        "name": "Bullish Short Seagull Spread", "category": "Other Combinations",
        "description": "Mirror of the bullish long seagull (buy the put, sell the call spread). Bearish-leaning income structure built from the same three strikes.",
        "legs": [_leg("PE", "BUY", -W), _leg("CE", "SELL", 0), _leg("CE", "BUY", W2)],
    },
    "bearish_long_seagull_spread": {
        "name": "Bearish Long Seagull Spread", "category": "Other Combinations",
        "description": "Sell an OTM call to help finance a bear put spread. Bearish, low net cost, but carries assignment risk on the short call if price rises hard.",
        "legs": [_leg("CE", "SELL", W), _leg("PE", "BUY", 0), _leg("PE", "SELL", -W2)],
    },
    "bearish_short_seagull_spread": {
        "name": "Bearish Short Seagull Spread", "category": "Other Combinations",
        "description": "Mirror of the bearish long seagull (buy the call, sell the put spread). Bullish-leaning income structure built from the same three strikes.",
        "legs": [_leg("CE", "BUY", W), _leg("PE", "SELL", 0), _leg("PE", "BUY", -W2)],
    },
}

# Aliases so both the short and long-form names people actually use resolve
CATALOG["iron_condor"] = CATALOG["long_iron_condor"]

CATEGORY_ORDER = [
    "Directional", "Covered & Protective", "Vertical Spreads", "Synthetic Positions",
    "Ladders", "Calendar & Diagonal", "Straddles, Strangles & Guts", "Synthetic Straddles",
    "Ratio Spreads & Backspreads", "Butterflies", "Condors", "Other Combinations",
]


def list_catalog():
    """[{key, name, category, description, multi_expiry}, ...], grouped-order friendly."""
    out = []
    for key, entry in CATALOG.items():
        if key == "iron_condor":
            continue  # alias, don't list twice
        out.append({
            "key": key,
            "name": entry["name"],
            "category": entry["category"],
            "description": entry["description"],
            "multi_expiry": entry.get("multi_expiry", False),
        })
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    out.sort(key=lambda e: (order.get(e["category"], 99), e["name"]))
    return out
