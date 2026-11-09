"""Yahoo inputs and shared command-line settings."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")


def inputs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    if args.download:
        download(config)
    output = Path("outputs")
    output.mkdir(exist_ok=True)
    return config, output


def clean_dates(frame):
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    return frame.loc[~frame.index.duplicated(keep="last")].sort_index()


def download(config):
    yf.set_tz_cache_location("data/yf-cache")
    for symbol in config["weights"]:
        folder = Path("data")/symbol
        folder.mkdir(parents=True, exist_ok=True)
        ticker = yf.Ticker(symbol)
        clean_dates(ticker.history(start=config["start"], end=config["end"], auto_adjust=False, actions=True)).to_csv(folder/"prices.csv")
        ticker.income_stmt.to_csv(folder/"income.csv")
        ticker.balance_sheet.to_csv(folder/"balance.csv")
        clean_dates(ticker.get_shares_full(start=config["start"], end=config["end"]).to_frame("shares")).to_csv(folder/"shares.csv")
        print(f"Downloaded {symbol}", flush=True)


def return_data(config):
    series = {}
    for symbol in config["weights"]:
        p = clean_dates(pd.read_csv(Path("data")/symbol/"prices.csv", index_col=0))
        series[symbol] = p["Adj Close"].loc[config["start"]:config["end"]].pct_change(fill_method=None)
    returns = pd.DataFrame(series).dropna()
    return returns, (returns @ pd.Series(config["weights"])).rename("portfolio_return")


def statement_row(frame, name):
    series = pd.to_numeric(frame.loc[name], errors="coerce")
    series.index = pd.to_datetime(series.index)
    return series.sort_index()


def annual_metrics(income, balance, lag):
    table = pd.concat({"equity":statement_row(balance,"Common Stock Equity"),
                       "income":statement_row(income,"Net Income Common Stockholders"),
                       "revenue":statement_row(income,"Total Revenue")}, axis=1).sort_index()
    prior = table.equity.shift()
    table["roe"] = (table.income/((table.equity+prior)/2)).where((table.equity>0)&(prior>0))
    table["growth"] = table.revenue.pct_change(fill_method=None).where(table.revenue.shift()>0)
    table.index += pd.Timedelta(days=lag)
    return table[["equity","roe","growth"]].rename_axis("available_proxy")


def build_panel(config):
    frames = []
    for symbol in config["weights"]:
        folder = Path("data")/symbol
        prices = clean_dates(pd.read_csv(folder/"prices.csv",index_col=0)).loc[config["start"]:config["end"]]
        shares = clean_dates(pd.read_csv(folder/"shares.csv",index_col=0))["shares"]
        annual = annual_metrics(pd.read_csv(folder/"income.csv",index_col=0),pd.read_csv(folder/"balance.csv",index_col=0),config["statement_lag_days"])
        p = pd.merge_asof(prices.rename_axis("date").reset_index(),annual.reset_index(),left_on="date",right_on="available_proxy",direction="backward",tolerance=pd.Timedelta(days=550)).set_index("date")
        shares = shares.reindex(shares.index.union(p.index)).sort_index().ffill().reindex(p.index)
        splits = p["Stock Splits"].replace(0,1)
        adjusted_shares = shares * splits.iloc[::-1].cumprod().iloc[::-1] / splits
        p["market_cap"] = p["Close"]*adjusted_shares
        p["adjusted_price"] = p["Adj Close"]
        p["return"] = p.adjusted_price.pct_change(fill_method=None)
        p["dividend_yield"] = p.Dividends.rolling("365D").sum()/p["Close"]
        p["turnover"] = p.Volume/adjusted_shares
        p["ticker"] = symbol
        frames.append(p)
    return pd.concat(frames).reset_index().set_index(["date","ticker"]).sort_index().replace([np.inf,-np.inf],np.nan)
