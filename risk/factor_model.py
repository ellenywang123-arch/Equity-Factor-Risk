"""Lagged factor-return regression and Euler factor attribution."""
import numpy as np
import pandas as pd

def regress(exposures, panel, minimum=35):
    # Shift each stock by one of ITS observed sessions; accept only adjacent benchmark dates.
    dates = panel.index.get_level_values("date").unique().sort_values()
    previous = dict(zip(dates[1:],dates[:-1]))
    lagged = exposures.groupby(level="ticker").shift(1)
    source_date = pd.Series(exposures.index.get_level_values("date"),index=exposures.index).groupby(level="ticker").shift(1)
    expected = pd.Series(exposures.index.get_level_values("date").map(previous),index=exposures.index)
    lagged.loc[source_date.ne(expected)] = np.nan
    sector = pd.get_dummies(panel["sector"],prefix="sector",dtype=float)
    sector = sector.loc[:,sorted(sector.columns)[1:]]  # first sector is reference
    design = lagged.join(sector).assign(market=1.)
    design = design[["market"]+list(sector.columns)+list(exposures.columns)]
    coefficients, residuals, ranks = [], [], []
    for date, section in design.groupby(level="date"):
        x = section.droplevel("date")
        y = panel.xs(date)["return"].reindex(x.index)
        valid = x.notna().all(axis=1)&y.notna()
        x,y=x.loc[valid],y.loc[valid]
        if len(x)<max(minimum,x.shape[1]+5):
            continue
        # Absent sectors produce zero columns: skip this date to keep consistent factors.
        coef,_,rank,_=np.linalg.lstsq(x.to_numpy(),y.to_numpy(),rcond=None)
        ranks.append({"date":date,"stocks":len(x),"rank":rank,"columns":x.shape[1]})
        if rank<x.shape[1]:
            continue
        coefficients.append(pd.Series(coef,index=x.columns,name=date))
        residuals.append((y-x@coef).rename(date))
    if not coefficients:
        raise ValueError("No full-rank regression dates; expand stock coverage or inspect sectors/data.")
    return pd.DataFrame(coefficients).sort_index(),pd.DataFrame(residuals).sort_index(),pd.DataFrame(ranks),design


def factor_attribution(X, F, weights):
    """Return b=X.T@w and each factor variance contribution b*(F@b)."""
    b = X.T @ weights
    return b, b * (F @ b)
