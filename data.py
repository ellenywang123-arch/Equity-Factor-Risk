"""Yahoo download/cache and an explicitly approximate annual-fundamental panel."""
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
import yfinance as yf


def clean_dates(frame):
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    return frame.loc[~frame.index.duplicated(keep="last")].sort_index()


def download(config, directory="data"):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(root / "yf-cache"))
    status = {}
    for symbol in dict.fromkeys(config["tickers"] + [config["benchmark"]]):
        folder = root / symbol
        folder.mkdir(exist_ok=True)
        try:
            ticker = yf.Ticker(symbol)
            history = clean_dates(ticker.history(start=config["start"], end=config["end"], auto_adjust=False, actions=True))
            if history.empty or "Adj Close" not in history:
                raise ValueError("No adjusted price history")
            history.to_csv(folder / "prices.csv")
            if symbol != config["benchmark"]:
                income, balance = ticker.income_stmt, ticker.balance_sheet
                if income.empty or balance.empty:
                    raise ValueError("Annual statements unavailable")
                income.to_csv(folder / "income.csv")
                balance.to_csv(folder / "balance.csv")
                shares = ticker.get_shares_full(start=config["start"], end=config["end"])
                if shares is None or shares.empty:
                    raise ValueError("Historical share counts unavailable")
                clean_dates(shares.to_frame("shares")).to_csv(folder / "shares.csv")
                (folder / "metadata.json").write_text(json.dumps({"sector": ticker.info.get("sector", "Unknown")}), encoding="utf-8")
            status[symbol] = "ok"
        except Exception as exc:
            status[symbol] = str(exc)
        print(symbol, status[symbol], flush=True)
        time.sleep(0.15)
    manifest = {"downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "config":config, "status":status}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if status.get(config["benchmark"]) != "ok":
        raise ValueError("Benchmark download failed; see data/manifest.json")
    return manifest


def statement_row(frame, name):
    if name not in frame.index:
        return pd.Series(dtype=float)
    series = pd.to_numeric(frame.loc[name], errors="coerce")
    series.index = pd.to_datetime(series.index)
    return series.sort_index()


def annual_metrics(income, balance, lag):
    """Fiscal-year values become usable after an ASSUMED lag, not verified filings."""
    revenue = statement_row(income, "Total Revenue")
    net = statement_row(income, "Net Income Common Stockholders")
    equity = statement_row(balance, "Common Stock Equity")
    table = pd.concat({"equity":equity, "income":net, "revenue":revenue}, axis=1).sort_index()
    prior_equity = table.equity.shift()
    gap = table.index.to_series().diff().dt.days.between(300, 430)
    mean_equity = (table.equity + prior_equity) / 2
    table["roe"] = (table.income / mean_equity).where((table.equity > 0) & (prior_equity > 0) & gap)
    table["growth"] = table.revenue.pct_change(fill_method=None).where((table.revenue.shift() > 0) & gap)
    table.index = table.index + pd.Timedelta(days=lag)
    return table[["equity", "income", "roe", "growth"]].rename_axis("available_proxy")


def build_panel(config, directory="data"):
    root = Path(directory)
    benchmark = clean_dates(pd.read_csv(root/config["benchmark"]/"prices.csv", index_col=0))
    market = benchmark["Adj Close"].pct_change(fill_method=None).rename("market_return")
    frames, audit = [], []
    for symbol in config["tickers"]:
        folder = root/symbol
        try:
            prices = clean_dates(pd.read_csv(folder/"prices.csv", index_col=0))
            shares = clean_dates(pd.read_csv(folder/"shares.csv", index_col=0))["shares"]
            income = pd.read_csv(folder/"income.csv", index_col=0)
            balance = pd.read_csv(folder/"balance.csv", index_col=0)
            annual = annual_metrics(income, balance, config["statement_lag_days"])
            # As-of join NEVER backfills statements before their assumed availability.
            p = pd.merge_asof(prices.rename_axis("date").reset_index(), annual.reset_index(), left_on="date", right_on="available_proxy", direction="backward", tolerance=pd.Timedelta(days=550)).set_index("date")
            p["shares"] = shares.reindex(shares.index.union(p.index)).sort_index().ffill().reindex(p.index)
            # Yahoo Close is split-adjusted. Put historical shares on the same split basis.
            split = p.get("Stock Splits", pd.Series(0., index=p.index)).replace(0, 1)
            future_split = split.iloc[::-1].cumprod().iloc[::-1] / split
            p["market_cap"] = p["Close"] * p.shares * future_split
            p["adjusted_price"] = p["Adj Close"]
            p["return"] = p.adjusted_price.pct_change(fill_method=None)
            p["market_return"] = market.reindex(p.index)
            # Yahoo dividend series and Close share the provider's split-adjusted basis.
            p["dividend_yield"] = p.get("Dividends", pd.Series(0., index=p.index)).rolling("365D").sum()/p["Close"]
            # Dollar-volume / market-cap is invariant to a consistent price scale.
            p["turnover"] = p.Volume / (p.shares * future_split)
            p["sector"] = json.loads((folder/"metadata.json").read_text())["sector"]
            p["ticker"] = symbol
            p = p.replace([np.inf, -np.inf], np.nan)
            frames.append(p)
            audit.append({"ticker":symbol,"rows":len(p),"duplicate_dates":int(p.index.duplicated().sum()),"missing_price":int(p.adjusted_price.isna().sum()),"nonpositive_price":int((p.adjusted_price<=0).sum()),"large_return_days":int((p["return"].abs()>.4).sum()),"status":"ok"})
        except Exception as exc:
            audit.append({"ticker":symbol,"status":str(exc)})
    if not frames:
        raise ValueError("No usable stock data; run --download and inspect data/manifest.json")
    return pd.concat(frames).reset_index().set_index(["date","ticker"]).sort_index(), pd.DataFrame(audit)
