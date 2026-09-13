"""
NIFTY Options Strategy Advisor -- Streamlit version.

Same backend as app.py (Flask) -- angel_auth, instruments, market_data,
strategies, strategy_engine, compute.py -- just a different frontend.
Run with: streamlit run streamlit_app.py
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import angel_auth
import instruments
import market_data
import strategies
import strategy_engine
from compute import compute_strategy

st.set_page_config(page_title="NIFTY Options Strategy Advisor", layout="wide")

# ---- App-level password gate ----
# Separate from your Angel One login -- required before this is ever
# reachable from the internet, since anyone who gets past it could use
# your live broker session. Skipped automatically if unset (local dev).
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

if APP_USERNAME and APP_PASSWORD and not st.session_state.get("app_authed"):
    st.title("Options Strategy Advisor")
    st.caption("Password protected")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Log in", type="primary"):
        if u == APP_USERNAME and p == APP_PASSWORD:
            st.session_state.app_authed = True
            st.rerun()
        else:
            st.error("Wrong username or password.")
    st.stop()

# ---- Angel One connection gate ----

if "connected" not in st.session_state:
    st.session_state.connected = angel_auth.is_connected()

if not st.session_state.connected:
    st.title("Options Strategy Advisor")
    st.caption("NIFTY · live via Angel One")
    st.write("Log in to your Angel One SmartAPI session to pull live spot, VIX, and option chain data.")
    if st.button("Connect to Angel One", type="primary"):
        try:
            session = angel_auth.login()
            st.session_state.connected = True
            st.session_state.client_code = session["client_code"]
            st.rerun()
        except Exception as e:
            st.error(str(e))
    st.stop()


# ---- Cached live data (short TTL so rapid reruns don't hammer the API) ----

@st.cache_data(ttl=15)
def cached_spot():
    return market_data.get_spot_price()


@st.cache_data(ttl=15)
def cached_vix():
    v = market_data.get_vix()
    return v, strategy_engine.classify_iv_regime(v)


@st.cache_data(ttl=3600)
def cached_expiries():
    return instruments.get_expiries()


@st.cache_data
def cached_catalog():
    return strategies.list_catalog()


# ---- Sidebar: ticker + controls ----

with st.sidebar:
    st.markdown(f"🟢 Connected as **{st.session_state.get('client_code', '')}**")

    try:
        spot = cached_spot()
    except Exception as e:
        spot = None
        st.warning(f"Spot unavailable: {e}")
    try:
        vix, iv_regime = cached_vix()
    except Exception as e:
        vix, iv_regime = None, None
        st.warning(f"VIX unavailable: {e}")

    c1, c2 = st.columns(2)
    c1.metric("Spot", f"₹{spot:,.2f}" if spot else "—")
    c2.metric("India VIX", f"{vix:.2f}" if vix else "—",
              (f"{'Low' if iv_regime == 'low' else 'High'} IV") if iv_regime else None)

    st.divider()

    mode = st.radio("Mode", ["Guided", "Browse all"], horizontal=True, label_visibility="collapsed")

    try:
        expiries = cached_expiries()
    except Exception as e:
        expiries = []
        st.error(f"Couldn't load expiries: {e}")

    catalog = cached_catalog()

    if mode == "Guided":
        expiry = st.selectbox("Expiry", expiries) if expiries else None
        direction = st.selectbox(
            "Your predicted direction", ["bullish", "bearish", "neutral"],
            format_func=lambda d: {"bullish": "Bullish", "bearish": "Bearish", "neutral": "Neutral / range-bound"}[d],
        )
        risk_pref = st.selectbox(
            "Risk preference", ["defined", "undefined"],
            format_func=lambda r: {"defined": "Defined risk (capped loss)", "undefined": "Open to uncapped risk"}[r],
        )
        st.caption("IV regime is read live from India VIX (cutoff in `config.py`) -- no manual guess needed.")
        go_clicked = st.button("Get suggestion", type="primary", use_container_width=True)
        strat_choice = None
    else:
        expiry = st.selectbox("Expiry", expiries) if expiries else None
        cat_names = list(dict.fromkeys(s["category"] for s in catalog))  # preserves catalog's own order
        category = st.selectbox("Category", cat_names)
        in_category = [s for s in catalog if s["category"] == category]
        strat_choice = st.selectbox(
            "Strategy", in_category,
            format_func=lambda s: s["name"] + (" (2 expiries)" if s["multi_expiry"] else ""),
        )
        st.caption(strat_choice["description"])
        go_clicked = st.button("Show strategy", type="primary", use_container_width=True)
        direction = risk_pref = None

    st.caption("Rule-based on standard options theory. Not financial advice — verify strikes and liquidity before placing anything.")

# ---- Run the strategy on click ----

if go_clicked and expiry:
    with st.spinner("Fetching live data…"):
        try:
            if mode == "Guided":
                v, regime = cached_vix()
                key = strategy_engine.pick_strategy(direction, regime, risk_pref)
                result = compute_strategy(key, expiry, vix=v, iv_regime=regime)
            else:
                try:
                    v, regime = cached_vix()
                except Exception:
                    v, regime = None, None
                result = compute_strategy(strat_choice["key"], expiry, vix=v, iv_regime=regime)
            st.session_state.result = result
            st.session_state.result_error = None
        except Exception as e:
            st.session_state.result_error = str(e)
            st.session_state.result = None

# ---- Results ----

if st.session_state.get("result_error"):
    st.error(f"Couldn't get that strategy: {st.session_state.result_error}")

r = st.session_state.get("result")
if r:
    st.subheader(r["strategy_name"])
    st.caption(r["description"])

    if r.get("vix") is not None:
        st.caption(f"India VIX right now: {r['vix']:.2f} ({'Low' if r['iv_regime'] == 'low' else 'High'} IV).")

    if r["multi_expiry"]:
        st.info(
            f"Two-expiry strategy: front leg(s) at {r['expiry']}, far leg(s) at {r['back_expiry']}. "
            f"Max profit/loss and the payoff curve value the far leg with Black-Scholes at today's IV "
            f"— a theoretical estimate, not a forecast."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net premium", f"₹{abs(r['net_premium']):.2f} {r['net_premium_type']}")
    m2.metric("Max profit", f"₹{r['max_profit']:.2f}")
    m3.metric("Max loss", f"₹{r['max_loss']:.2f}")
    m4.metric("Breakeven(s)", ", ".join(f"{b:.0f}" for b in r["breakevens"]) if r["breakevens"] else "—")

    legs_df = pd.DataFrame([{
        "Action": l["action"],
        "Contract": l["symbol"] or "—",
        "Strike": "—" if l["instr"] == "FUT" else l["strike"],
        "Type": "FUT" if l["instr"] == "FUT" else (l["instr"] + (" · far" if l["expiry_role"] == "back" else "")),
        "Qty": l["qty"],
        "Price": l["ltp"],
    } for l in r["legs"]])
    st.dataframe(legs_df, hide_index=True, use_container_width=True)

    # Payoff diagram -- two traces (profit/loss) so the fill colors split at zero
    curve = r["payoff_curve"]
    xs = [p[0] for p in curve]
    ys = [p[1] for p in curve]
    ys_pos = [y if y >= 0 else None for y in ys]
    ys_neg = [y if y < 0 else None for y in ys]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys_pos, mode="lines", line=dict(color="#4E9E77", width=2),
                              fill="tozeroy", fillcolor="rgba(78,158,119,0.15)", name="Profit"))
    fig.add_trace(go.Scatter(x=xs, y=ys_neg, mode="lines", line=dict(color="#C0503F", width=2),
                              fill="tozeroy", fillcolor="rgba(192,80,63,0.15)", name="Loss"))
    fig.add_hline(y=0, line_color="#2A303B")
    fig.add_vline(x=r["spot"], line_dash="dash", line_color="#8B93A1",
                  annotation_text=f"spot {r['spot']:.0f}", annotation_position="top")
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False, plot_bgcolor="#1C2129", paper_bgcolor="#1C2129",
        font_color="#E8E6E1", xaxis=dict(gridcolor="#2A303B"), yaxis=dict(gridcolor="#2A303B"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Option chain
    st.subheader("Option chain")
    chain = r["chain"]
    if chain:
        strikes = sorted(chain.keys())
        atm = min(strikes, key=lambda s: abs(s - r["spot"]))
        rows = []
        for s in strikes:
            ce = chain[s].get("CE", {})
            pe = chain[s].get("PE", {})
            rows.append({
                "Call OI": ce.get("volume"), "Call IV": ce.get("iv"), "Call Delta": ce.get("delta"), "Call LTP": ce.get("ltp"),
                "Strike": s,
                "Put LTP": pe.get("ltp"), "Put Delta": pe.get("delta"), "Put IV": pe.get("iv"), "Put OI": pe.get("volume"),
            })
        chain_df = pd.DataFrame(rows)

        def _highlight_atm(row):
            is_atm = row["Strike"] == atm
            return ["background-color: rgba(201,162,39,0.12)" if is_atm else "" for _ in row]

        st.dataframe(chain_df.style.apply(_highlight_atm, axis=1), hide_index=True,
                     use_container_width=True, height=420)
    else:
        st.caption("No chain data.")
