"""Eight MSCI-inspired style proxies; no proprietary MSCI model is reproduced."""
import numpy as np
import pandas as pd

STYLES = ["value","size","momentum","volatility","quality","yield","growth","liquidity"]


def raw_factors(panel):
    outputs = []
    for ticker, p in panel.groupby(level="ticker"):
        p = p.droplevel("ticker").sort_index()
        r = p["return"]
        x = pd.DataFrame(index=p.index)
        x["value"] = (p.equity/p.market_cap).where((p.equity>0)&(p.market_cap>0))
        x["size"] = np.log(p.market_cap.where(p.market_cap>0))
        x["momentum"] = p.adjusted_price.shift(21)/p.adjusted_price.shift(252)-1
        x["volatility"] = r.rolling(60, min_periods=60).std(ddof=1)*np.sqrt(252)
        x["quality"] = p.roe
        x["yield"] = p.dividend_yield
        x["growth"] = p.growth
        x["liquidity"] = p.turnover.rolling(60,min_periods=60).mean().where(p.turnover>0)
        x["ticker"] = ticker
        outputs.append(x)
    return pd.concat(outputs).rename_axis("date").reset_index().set_index(["date","ticker"]).sort_index().replace([np.inf,-np.inf],np.nan)

