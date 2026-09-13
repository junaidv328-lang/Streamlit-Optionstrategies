# NIFTY Options Strategy Advisor

# NIFTY Options Strategy Advisor

Two frontends, one shared backend:

- **`app.py`** — the original Flask + hand-built HTML/JS version, with
  the custom dark trading-terminal styling.
- **`streamlit_app.py`** — a Streamlit rebuild of the same tool, for
  hosts that run Streamlit natively. **Not for Streamlit Community
  Cloud** — its Terms of Use explicitly exclude apps that process
  financial information, which this does (live data tied to your
  personal broker session). Run it yourself: locally, on a VPS, or on
  a host like Render that just runs your `streamlit run` command
  rather than routing through Streamlit's own cloud service.

Both import the same `angel_auth.py`, `instruments.py`,
`market_data.py`, `strategies.py`, `strategy_engine.py`, and
`compute.py` — so a fix to the backend (data fetching, leg-building,
payoff math) applies to both frontends automatically. Only the UI
layer differs.

Opens on a connection screen — click **Connect to Angel One** to start
a SmartAPI session (explicit, not silent on first click elsewhere).
Once connected:

- **Guided** — pick your predicted direction and risk preference; IV
  regime is read live from India VIX (no manual guess), and it
  suggests one of 9 core strategies.
- **Browse all** — pick any of the full ~60-strategy catalog directly
  (covered calls, ladders, calendar/diagonal spreads, synthetic
  straddles, butterflies, condors, seagull spreads, and more).

Either way you get the exact option contracts (tradingsymbol, strike,
expiry, call/put, buy/sell) making up the strategy, net premium, max
profit/loss, breakevens, and a payoff diagram — all computed off the
live NIFTY option chain and India VIX via Angel One SmartAPI.

The strategy names and construction (bull/bear spreads, iron condors,
seagull spreads, etc.) are standard, widely-taught options theory —
generic industry terminology, not derived from any single book. See
`strategies.py` for the full catalog and `strategy_engine.py` for the
leg-building and payoff math.

## How IV regime works now

`config.VIX_LOW_HIGH_CUTOFF` (default 15.0) is the single line splitting
live India VIX into "low" / "high" for the guided rule table. It's a
static number, not derived from current data — India VIX has roughly
run ~11-15 in calm periods and spiked well above 20 in stress, but
"roughly" is doing a lot of work in that sentence. Adjust the cutoff
in `config.py` if it doesn't match what you'd actually call high IV
right now, and treat `strategy_engine.classify_iv_regime()` as a
starting heuristic, not a calibrated model.

## The full catalog

`strategies.py` has ~60 strategies across 12 categories: Directional,
Covered & Protective, Vertical Spreads, Synthetic Positions, Ladders,
Calendar & Diagonal, Straddles/Strangles/Guts, Synthetic Straddles,
Ratio Spreads & Backspreads, Butterflies, Condors, and Other
Combinations (box, collar, seagull spreads). A few things worth
knowing about how they're built:

- **"Covered" and "protective" strategies use NIFTY futures as the
  underlying**, not stock — there's no NIFTY share to actually hold.
  `instruments.get_front_month_future()` finds the nearest-expiry
  futures contract for this.
- **Calendar and diagonal spreads need two expiries** (a near leg and
  a far leg). The far leg hasn't expired when the near leg does, so
  its value at that point is estimated with Black-Scholes using
  today's IV — a reasonable approximation, not a forecast of where IV
  will actually be. The UI flags these as "2 expiries" in the picker
  and shows a note when you select one.
- **Ratio spreads, backspreads, and butterflies use unequal leg
  quantities** (e.g. buy 1, sell 2) — each leg in `strategies.py`
  carries a `qty` multiplier for this.
- Strike spacing is controlled by `W` and `W2` in `strategies.py`
  (100 and 200 points on NIFTY) — adjust there if you want wider or
  tighter structures across the board.

## Setup

```bash
pip install -r requirements.txt
cp .env.template .env
# fill in .env with your Angel One API key, client code, password, and TOTP secret
python app.py
```

Then open `http://localhost:5000`.

## Running the Streamlit version instead

Same `.env` setup as above, then:

```bash
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. The `.streamlit/config.toml` in this
project sets a dark theme approximating the Flask version's look using
Streamlit's own theming, not custom CSS. If you deploy this version
anywhere reachable from the internet (not Streamlit Community Cloud —
see above), set `APP_USERNAME`/`APP_PASSWORD` in that host's
environment first, same as the Flask version.

## Things to verify before trusting this with real money

1. **Auth headers and API domain** (`angel_auth.py`, `config.BASE_URL`) —
   fixed: the app originally pointed at `apiconnect.angelbroking.com`,
   which is stale — Angel Broking rebranded to Angel One and the
   confirmed production domain (from the official `smartapi-python`
   SDK source) is `apiconnect.angelone.in`. Also added a defensive
   strip of any pre-existing `Bearer ` prefix on the JWT before
   formatting the Authorization header, per a gotcha reported on
   Angel One's forum. If auth still fails, `get_session()` /
   `auth_headers()` in `angel_auth.py` are the two functions to swap
   for a working login module from ScalpEdge or the chart pattern app.

2. **Option Greeks API is unreliable — by design, not a bug here.**
   Angel One's `optionGreek` endpoint has a long-running, widely
   reported issue (errorcode `AB9019`, "No Data Available") that hits
   correctly-formatted requests for many users on their own forum,
   unresolved over an extended period. `market_data.get_option_chain()`
   now treats a Greeks failure as non-fatal — delta/gamma/theta/vega/IV
   just show blank in the chain table, since strategy pricing runs off
   LTP (a different, more reliable endpoint) either way. There's also a
   separate, still-unverified report of this endpoint returning monthly
   Greeks for a weekly-expiry request — worth spot-checking when it
   *is* returning data.

3. **Strike step / wing width** — hardcoded to NIFTY's 50-point step
   with a 2-step (100-point) wing for spreads/condors (`W`, `W2` in
   `strategies.py`). Adjust there if you want tighter or wider
   structures across the board.

4. **Payoff math is at-expiry, not live P/L** — `payoff_at()` uses
   intrinsic value at a hypothetical settlement price, not current
   mark-to-market. That's standard for a strategy-selection tool but
   don't read it as today's live P/L on the position.

5. **Rule table is a starting point, not a complete system** — it
   doesn't account for skew, upcoming events (RBI policy, expiry-day
   pinning, budget day), or position sizing. Treat the suggestion as
   a shortlist of one reasonable structure for your stated view, not
   a final call.

6. **Seagull spread construction varies by source** — "bullish/
   bearish" and "long/short" seagull naming isn't fully standardized
   across textbooks. `strategies.py` uses one common 3-leg
   definition (see the descriptions in the browse picker); check the
   legs table against what you actually mean before trusting it.

7. **Futures leg pricing** (`market_data.get_futures_price`) assumes
   the scrip master's `FUTIDX` rows for NIFTY are current and that the
   nearest-expiry contract is the one you want — same
   untested-live caveat as the options endpoints above.

## Project layout

```
config.py            credentials + constants (reads .env)
angel_auth.py         SmartAPI login/session
instruments.py         NIFTY option + futures instrument lookup (scrip master)
market_data.py         spot price, futures price, VIX, merged option chain (Greeks + LTP)
strategies.py           the ~60-strategy catalog (names, descriptions, leg templates)
strategy_engine.py     guided-mode rules + generic leg-building and payoff/breakeven math
compute.py              shared orchestration (fetch + build + price one strategy) -- used by both frontends
app.py                 Flask API + serves static/ -- run with `python app.py` or `gunicorn app:app`
streamlit_app.py       Streamlit frontend on the same backend -- run with `streamlit run streamlit_app.py`
static/                Flask version's HTML/CSS/JS
.streamlit/config.toml  Streamlit version's theme
Procfile                Render start command for the Flask version (gunicorn)
```

## Extending to BANKNIFTY / other symbols later

`instruments.py` and `market_data.py` are hardcoded to `name ==
"NIFTY"` and the NIFTY 50 spot token. To add another index, you'd
parameterize those two by symbol + spot token, and add a symbol
selector to the frontend.
