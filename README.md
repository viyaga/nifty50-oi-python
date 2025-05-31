# NSE Option-Chain FastAPI Service

This project continuously fetches the NIFTY option-chain JSON (CE/PE total OI) from NSE every 60 seconds and exposes a FastAPI endpoint (`GET /`) that returns the latest CE/PE total OI.

## Folder Structure

nse-fastapi/
├── main.py
├── requirements.txt
└── README.md

bash
Copy
Edit

## Installation

1. **Clone the repository** (or copy files into a directory on your machine/cloud server):
   ```bash
   git clone <your-repo-URL> nse-fastapi
   cd nse-fastapi
Create and activate a virtual environment (strongly recommended):

bash
Copy
Edit
# On Linux/macOS:
python3 -m venv venv
source venv/bin/activate

# On Windows:
python -m venv venv
venv\Scripts\activate
Install Python dependencies:

bash
Copy
Edit
pip install --upgrade pip
pip install -r requirements.txt
The packages installed are:

fastapi (the web framework)

uvicorn[standard] (ASGI server)

requests (for HTTP requests to NSE)

Verify Python version
We recommend Python 3.9+. You can check your Python version with:

bash
Copy
Edit
python --version
Usage
Run the FastAPI server:

bash
Copy
Edit
uvicorn main:app --reload
By default, Uvicorn will start at http://127.0.0.1:8000.

The --reload flag automatically restarts the server whenever you modify main.py.

Access the endpoint:
Open your browser or use curl to fetch CE/PE total OI:

bash
Copy
Edit
curl http://127.0.0.1:8000/
On the first few seconds, you might get a 503 (data not yet available). Simply retry after ~10 seconds.

After the background task fetches data, you’ll see a JSON response like:

json
Copy
Edit
{
  "CE": { "totalOI": 12345678 },
  "PE": { "totalOI": 87654321 }
}
Deploying to a Cloud Environment

Because this implementation uses plain HTTP requests (no Selenium/Playwright), it runs out-of-the-box on most Linux servers, Docker containers, or serverless platforms (AWS/GCP/Azure) without needing Xvfb or any GUI.

In a cloud VM or container, simply install Python 3.9+, clone the repo, install requirements, and run:

bash
Copy
Edit
uvicorn main:app --host 0.0.0.0 --port 8000
Ensure your cloud instance’s outbound firewall allows HTTPS traffic to nseindia.com.

How It Works
Cookie Acquisition

When the server starts, main.py calls _refresh_nse_cookies() once:

GET https://www.nseindia.com (homepage)

GET https://www.nseindia.com/option-chain (option-chain landing)

This populates session.cookies with all Akamai cookies needed to access the JSON API.

Periodic Polling

_background_fetch_loop() is launched as a FastAPI startup task.

Every 60 seconds, it calls _fetch_option_chain_json():

If cookies are older than 10 minutes, first refresh them by repeating step 1.

Then GET https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY with the cookies.

If that API request returns 401/403, the code immediately refreshes cookies and retries once.

Cache & Endpoint

On successful fetch, the code extracts:

python
Copy
Edit
ce_oi = data["filtered"]["CE"]["totOI"]
pe_oi = data["filtered"]["PE"]["totOI"]
and stores them in the in-memory cache with a timestamp.

When you GET /, FastAPI returns the latest cached totals (or a 503 if the service hasn’t fetched anything yet).

Customization
Polling Interval

Change API_POLL_INTERVAL = 60 (in main.py) if you want data more or less frequently.

Cookie Refresh Interval

By default, cookies refresh every 600 seconds (10 minutes). Change COOKIE_REFRESH_INTERVAL if NSE’s Akamai cookies expire faster/slower.

Troubleshooting
503 on first request

The background task needs a few seconds to fetch initial cookies + JSON. Retry after ~10 seconds.

“401 Unauthorized” or “403 Forbidden”

This means cookies expired (or didn’t set properly). The code tries one immediate refresh on a 401/403. If it keeps failing:

Confirm your server can reach https://www.nseindia.com and has no IP restrictions.

Make sure the User-Agent header in session.headers is a valid, up-to-date browser string. You may swap in the latest Chrome/Firefox UA if NSE has tightened checks.

No data in cache

If you see "error": "Data not yet available; try again in a few seconds." for more than 30 seconds, check your server logs: you should see prints like:

objectivec
Copy
Edit
🚀 Starting background task to fetch NSE data every 60 seconds.
🕒 Cookies expired or missing; refreshing cookies.
✅ Refreshed NSE cookies: {...}
✅ Updated cache: {'CE': {'totalOI': ...}, 'PE': {'totalOI': ...}}
If you only see errors refreshing cookies or fetching JSON, verify network connectivity to nseindia.com.

Server Crash / Missing Dependencies

Ensure you ran pip install -r requirements.txt.

Confirm Python 3.9+ is active in your virtual environment.

Example Run
bash
Copy
Edit
# 1) Start a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3) Launch the app (listening on all interfaces, port 8000)
uvicorn main:app --host 0.0.0.0 --port 8000
In another terminal, check the data:

bash
Copy
Edit
curl http://127.0.0.1:8000/
# → If you see {"error": "..."} simply wait ~10 seconds and try again.
# → Soon you will see something like:
# {
#   "CE": { "totalOI": 14532000 },
#   "PE": { "totalOI": 13245000 }
# }
Copy
Edit