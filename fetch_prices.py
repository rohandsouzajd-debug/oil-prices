"""Fetch settled oil futures closes from Yahoo Finance and save them to prices.json.
Runs in GitHub Actions every weekday evening (see .github/workflows/prices.yml)."""
import datetime as dt
import json
import time
from zoneinfo import ZoneInfo

import yfinance as yf

TICKERS = {
    "brent": ("BZ=F", "Brent crude futures, $/bbl"),
    "wti": ("CL=F", "WTI crude futures, $/bbl"),
    "ulsd": ("HO=F", "NYMEX ULSD (diesel) futures, $/gal"),
    "rbob": ("RB=F", "NYMEX RBOB (gasoline) futures, $/gal"),
}


def settled_closes(ticker, period):
    last_err = None
    for attempt in range(4):
        try:
            h = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)["Close"].dropna()
            if len(h) >= 2:
                break
        except Exception as e:
            last_err = e
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"No data for {ticker}: {last_err}")
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    rows = []
    for idx, close in h.items():
        d = idx.date()
        if d > now.date() or (d == now.date() and now.hour < 17):
            continue  # session still trading
        rows.append([d.isoformat(), round(float(close), 4)])
    return rows


def main():
    out = {"updated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "source": "Yahoo Finance (yfinance)"}
    for key, (ticker, desc) in TICKERS.items():
        rows = settled_closes(ticker, "1y" if key == "brent" else "1mo")
        out[key] = {"ticker": ticker, "description": desc,
                    "date": rows[-1][0], "close": rows[-1][1],
                    "prev_date": rows[-2][0], "prev_close": rows[-2][1],
                    "history": rows[-15:]}
        if key == "brent":
            lo = min(rows[-260:], key=lambda r: r[1])
            hi = max(rows[-260:], key=lambda r: r[1])
            out["brent_52w"] = {"low": lo[1], "low_date": lo[0], "high": hi[1], "high_date": hi[0]}
    out["session_date"] = out["brent"]["date"]
    out["dates_match"] = len({out[k]["date"] for k in TICKERS}) == 1
    with open("prices.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: (out[k]["date"], out[k]["close"]) for k in TICKERS}))


if __name__ == "__main__":
    main()
