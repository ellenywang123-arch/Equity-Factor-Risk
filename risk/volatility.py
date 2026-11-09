"""Model covariance, portfolio volatility and optional past-only calibration."""
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from .factor_model import factor_attribution

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
    b,factor_contribution=factor_attribution(X,F,w)
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
