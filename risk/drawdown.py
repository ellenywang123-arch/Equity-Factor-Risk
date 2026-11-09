"""Fixed-weight daily-rebalanced illustrative NAV and drawdown, not a live record."""
import numpy as np
import pandas as pd


def portfolio_returns(panel, weights, as_of):
    """Require complete held-stock returns after their first common valid session."""
    w = pd.Series(weights, dtype=float)
    if not np.isfinite(w).all() or not np.isclose(w.sum(), 1):
        raise ValueError("Finite weights must sum to one")
    wide = panel["return"].unstack("ticker").sort_index().loc[:as_of]
    if not w.index.isin(wide.columns).all():
        raise ValueError("Held stock missing from return data")
    wide = wide.reindex(columns=w.index)
    complete = wide.notna().all(axis=1)
    if not complete.any():
        raise ValueError("No common held-stock return history")
    wide = wide.loc[complete[complete].index[0]:]
    if wide.isna().any().any() or not np.isfinite(wide.to_numpy()).all():
        raise ValueError("Internal gaps in held-stock returns; do not silently renormalize weights")
    result = wide @ w
    if (result <= -1).any():
        raise ValueError("NAV cannot be compounded through a loss of 100% or more")
    return result.rename("portfolio_return")


def drawdown_series(returns):
    """Include starting NAV=1 when determining the running high-water mark."""
    if returns.empty or not np.isfinite(returns).all() or (returns <= -1).any():
        raise ValueError("Provide finite simple returns above -100%")
    nav = (1+returns).cumprod()
    peak = nav.cummax().clip(lower=1.)
    dd = nav/peak-1
    return pd.DataFrame({"portfolio_return":returns, "nav":nav, "drawdown":dd})


def drawdown_summary(path):
    return {"current_drawdown":float(path.drawdown.iloc[-1]),
            "max_drawdown":float(path.drawdown.min()),
            "drawdown_start":str(path.index[0].date()),
            "drawdown_end":str(path.index[-1].date()),
            "drawdown_observations":len(path)}
