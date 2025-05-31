# main.py

import time
import requests
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

# ----------------------------------------------------------------
#  In-memory cache for “totals” and a timestamp
#  This will be updated every 60 seconds by a background task
# ----------------------------------------------------------------
cache = {
    "timestamp": 0,
    "totals": {"CE": {"totalOI": 0}, "PE": {"totalOI": 0}},
}

# ----------------------------------------------------------------
#  Global variables for managing cookies
# ----------------------------------------------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/116.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
})

COOKIE_REFRESH_INTERVAL = 600  # seconds (10 minutes)
API_POLL_INTERVAL = 60        # seconds (1 minute)
_last_cookie_time = 0
_cookies = {}  # will store the latest cookies as a dict


def _refresh_nse_cookies() -> None:
    """
    Load NSE homepage and option-chain landing page to set Akamai cookies.
    Updates the module-level `_cookies` dict and `_last_cookie_time`.
    """
    global _cookies, _last_cookie_time

    try:
        # 1) Hit the NSE homepage to obtain initial session cookies
        resp_home = session.get("https://www.nseindia.com", timeout=10)
        resp_home.raise_for_status()

        # 2) Hit the option-chain landing page so NSE sets cookies specific to that page
        resp_chain = session.get("https://www.nseindia.com/option-chain", timeout=10)
        resp_chain.raise_for_status()

        # 3) Now grab whatever cookies we have in the session
        _cookies = session.cookies.get_dict()
        _last_cookie_time = time.time()
        print("✅ Refreshed NSE cookies:", _cookies)

    except Exception as e:
        print(f"❌ Error refreshing NSE cookies: {e}")
        # If fetching cookies fails, keep any old cookies (if present). 
        # Next cycle will try again.


def _fetch_option_chain_json() -> dict | None:
    """
    Fetches the raw JSON from the NSE option-chain API, using the current cookies.
    If cookies are older than COOKIE_REFRESH_INTERVAL, refresh them first.
    If the request returns 401/403, attempt one immediate refresh + retry.
    Returns the parsed JSON dict, or None on failure.
    """
    global _cookies, _last_cookie_time

    now = time.time()
    # 1) Refresh cookies if > 10 minutes have passed or if no cookies exist yet
    if now - _last_cookie_time > COOKIE_REFRESH_INTERVAL or not _cookies:
        print("🕒 Cookies expired or missing; refreshing cookies.")
        _refresh_nse_cookies()

    api_url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

    try:
        resp = session.get(
            api_url,
            headers={
                # JSON API expects slightly different Accept header
                "User-Agent": session.headers["User-Agent"],
                "Accept-Language": session.headers["Accept-Language"],
                "Accept": "application/json, text/plain, */*",
                "Connection": session.headers["Connection"],
                "Referer": "https://www.nseindia.com/option-chain",
            },
            cookies=_cookies,
            timeout=10
        )
        # If unauthorized/forbidden, refresh cookies immediately and retry once
        if resp.status_code in (401, 403):
            print(f"⚠️ NSE API returned {resp.status_code}. Refreshing cookies and retrying.")
            _refresh_nse_cookies()
            resp = session.get(
                api_url,
                headers={
                    "User-Agent": session.headers["User-Agent"],
                    "Accept-Language": session.headers["Accept-Language"],
                    "Accept": "application/json, text/plain, */*",
                    "Connection": session.headers["Connection"],
                    "Referer": "https://www.nseindia.com/option-chain",
                },
                cookies=_cookies,
                timeout=10
            )

        resp.raise_for_status()
        data = resp.json()
        return data

    except Exception as e:
        print(f"❌ Error fetching option-chain JSON: {e}")
        return None


def _update_totals_from_json(data: dict) -> None:
    """
    Extract CE/PE total OI from the raw JSON and update the in-memory cache.
    """
    ce_oi = data.get("filtered", {}).get("CE", {}).get("totOI", 0)
    pe_oi = data.get("filtered", {}).get("PE", {}).get("totOI", 0)

    new_totals = {
        "CE": {"totalOI": ce_oi},
        "PE": {"totalOI": pe_oi},
    }

    cache["timestamp"] = time.time()
    cache["totals"] = new_totals
    print("✅ Updated cache:", new_totals)


async def _background_fetch_loop() -> None:
    """
    Async background task that runs forever:
      • Every API_POLL_INTERVAL seconds, fetch fresh JSON and update cache.
      • If fetching fails, wait a short interval and retry.
    """
    # Ensure cookies are loaded at least once before entering the loop
    if not _cookies:
        _refresh_nse_cookies()

    while True:
        try:
            data = _fetch_option_chain_json()
            if data:
                _update_totals_from_json(data)
            else:
                print("⚠️ Received no data. Will retry on next cycle.")
        except Exception as e:
            print("❌ Unexpected exception in background loop:", e)

        # Wait for the next cycle
        await asyncio.sleep(API_POLL_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event: launch the background fetch loop.
    """
    print("🚀 Starting background task to fetch NSE data every 60 seconds.")
    asyncio.create_task(_background_fetch_loop())


@app.get("/")
async def get_option_totals():
    """
    GET "/" endpoint:
      • If cache is populated (timestamp > 0), return the CE/PE totals.
      • If cache is still empty (first few seconds after startup), return a 503.
    """
    if cache["timestamp"] == 0:
        # Service hasn’t fetched data yet
        return JSONResponse(
            status_code=503,
            content={"error": "Data not yet available; try again in a few seconds."}
        )

    return JSONResponse(content=cache["totals"])
