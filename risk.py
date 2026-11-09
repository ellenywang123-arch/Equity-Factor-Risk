"""Lagged cross-sectional regression, shrinkage covariance and Euler contributions."""
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


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


def covariance(factor_returns, residuals, minimum=126):
    if len(factor_returns)<minimum:
        raise ValueError(f"Need {minimum} valid history days; have {len(factor_returns)}")
    estimator=LedoitWolf().fit(factor_returns.to_numpy())
    F=pd.DataFrame(estimator.covariance_,index=factor_returns.columns,columns=factor_returns.columns)
    D=residuals.var(ddof=1).where(residuals.count()>=minimum)
    # Missing variances remain missing. Never substitute zero risk.
    return F,D,float(estimator.shrinkage_)


def portfolio_risk(X,F,D,weights):
    """Daily RETURN variance decomposition; contributions may be negative."""
    w=pd.Series(weights,dtype=float)
    if not np.isfinite(w).all() or not np.isclose(w.sum(),1):
        raise ValueError("Finite weights must sum to one")
    if not w.index.isin(X.index).all():
        raise ValueError("A held stock has no valid current exposures")
    X=X.reindex(index=w.index,columns=F.index)
    d=D.reindex(w.index)
    if X.isna().any().any() or d.isna().any() or (d<0).any():
        raise ValueError("Held stocks have missing exposures or insufficient residual history")
    b=X.T@w
    factor_contribution=b*(F@b)
    specific_contribution=w.pow(2)*d
    total=float(factor_contribution.sum()+specific_contribution.sum())
    if total<=0:
        raise ValueError("Nonpositive portfolio variance")
    sigma=np.sqrt(total)
    table=pd.DataFrame({"exposure":b,"daily_variance_contribution":factor_contribution,"total_variance_share":factor_contribution/total,"annual_vol_contribution":factor_contribution/sigma*np.sqrt(252)})
    summary={"annual_volatility":float(sigma*np.sqrt(252)),"daily_variance":total,"factor_variance_share":float(factor_contribution.sum()/total),"specific_variance_share":float(specific_contribution.sum()/total)}
    return summary,table,specific_contribution


def rolling_validation(f,eps,design,panel,weights,window=252,minimum=126):
    """Next-day squared-return calibration; every fit uses only past observations."""
    records=[]
    for date in f.index[minimum:]:
        past=f.loc[f.index<date].tail(window)
        F,D,_=covariance(past,eps.reindex(past.index),minimum)
        try:
            summary,_,_=portfolio_risk(design.xs(date),F,D,weights)
            realized=panel.xs(date)["return"].reindex(weights)
            if realized.isna().any():
                continue
            r=float(realized@pd.Series(weights))
            records.append({"date":date,"predicted_daily_variance":summary["daily_variance"],"realized_return":r,"realized_squared_return":r*r})
        except ValueError:
            continue
    return pd.DataFrame(records)
