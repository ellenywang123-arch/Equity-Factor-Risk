"""Yahoo download/cache and an explicitly approximate annual-fundamental panel."""
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
import yfinance as yf
import argparse
import matplotlib
matplotlib.use("Agg")


def inputs():
    """Shared arguments only; each risk module performs its own calculation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    w = pd.Series(config["weights"], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1):
        raise ValueError("Long-only weights must be finite and sum to one")
    if config["confidence"] != 0.95:
        raise ValueError("This simplified project uses confidence=0.95")
    if args.download:
        download(config)
    output = Path("outputs")
    output.mkdir(exist_ok=True)
    return config, output


def return_data(config, directory="data"):
    """Read ONLY held-stock prices; no financial statements needed for market risk."""
    series = {}
    for symbol in config["weights"]:
        p = clean_dates(pd.read_csv(Path(directory)/symbol/"prices.csv", index_col=0))
        p = p.loc[config["start"]:config.get("end")]
        if (p["Adj Close"].dropna() <= 0).any():
            raise ValueError(f"Nonpositive price: {symbol}")
        series[symbol] = p["Adj Close"].pct_change(fill_method=None)
    returns = pd.DataFrame(series).sort_index()
    valid = returns.notna().all(axis=1)
    if not valid.any():
        raise ValueError("No common holding history")
    returns = returns.loc[valid[valid].index[0]:]
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Missing internal holding returns; weights will not be renormalized")
    portfolio = (returns @ pd.Series(config["weights"])).rename("portfolio_return")
    if (portfolio <= -1).any():
        raise ValueError("Cannot compound a loss of 100% or more")
    return returns, portfolio


def clean_dates(frame):
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    return frame.loc[~frame.index.duplicated(keep="last")].sort_index()


def download(config, directory="data"):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(root / "yf-cache"))
    status = {}
    for symbol in config["weights"]:
        folder = root / symbol
        folder.mkdir(exist_ok=True)
        try:
            ticker = yf.Ticker(symbol)
            history = clean_dates(ticker.history(start=config["start"], end=config["end"], auto_adjust=False, actions=True))
            if history.empty or "Adj Close" not in history:
                raise ValueError("No adjusted price history")
            history.to_csv(folder / "prices.csv")
            income, balance = ticker.income_stmt, ticker.balance_sheet
            if income.empty or balance.empty:
                raise ValueError("Annual statements unavailable")
            income.to_csv(folder / "income.csv")
            balance.to_csv(folder / "balance.csv")
            shares = ticker.get_shares_full(start=config["start"], end=config["end"])
            if shares is None or shares.empty:
                raise ValueError("Historical share counts unavailable")
            clean_dates(shares.to_frame("shares")).to_csv(folder / "shares.csv")

            status[symbol] = "ok"
        except Exception as exc:
            status[symbol] = str(exc)
        print(symbol, status[symbol], flush=True)
        time.sleep(0.15)
    manifest = {"downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "config":config, "status":status}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if any(v != "ok" for v in status.values()):
        raise ValueError("A held stock download failed; retry rather than omit the holding")
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
    frames = []
    for symbol in config["weights"]:
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
            # Yahoo dividend series and Close share the provider's split-adjusted basis.
            p["dividend_yield"] = p.get("Dividends", pd.Series(0., index=p.index)).rolling("365D").sum()/p["Close"]
            # Dollar-volume / market-cap is invariant to a consistent price scale.
            p["turnover"] = p.Volume / (p.shares * future_split)
            p["ticker"] = symbol
            p = p.replace([np.inf, -np.inf], np.nan)
            frames.append(p)
        except Exception as exc:
            raise ValueError(f"Cannot load held stock {symbol}: {exc}") from exc
    if not frames:
        raise ValueError("No usable stock data; run --download and inspect data/manifest.json")
    return pd.concat(frames).reset_index().set_index(["date","ticker"]).sort_index()
