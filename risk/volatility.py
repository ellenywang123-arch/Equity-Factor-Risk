"""Eight-style-plus-intercept risk model and historical covariance comparison."""
import numpy as np
import pandas as pd
from data import inputs, return_data
from .factor_model import fit_model
import matplotlib.pyplot as plt


def portfolio_volatility(returns, weights, window=252):
    history = returns.tail(window)
    covariance = history.cov()
    w = pd.Series(weights).reindex(covariance.index)
    annual = float(np.sqrt(w @ covariance @ w * 252))
    return annual, covariance


def model_volatility(model, weights, window=252):
    """Sample factor covariance plus diagonal residual variance; no sector terms."""
    f = model["factor_returns"].tail(window)
    eps = model["residuals"].reindex(f.index)
    F = f.cov()
    d = eps.var(ddof=1)
    X = model["z"].assign(market=1.).reindex(columns=F.columns)
    w = pd.Series(weights).reindex(X.index)
    d = d.reindex(X.index)
    b = X.T @ w
    variance = float(b @ F @ b + (w.pow(2)*d).sum())
    return float(np.sqrt(252*variance)), len(f)


if __name__ == "__main__":
    config, output = inputs()
    model = fit_model(config)
    model_annual, history_days = model_volatility(model,config["weights"],config["window"])
    returns, portfolio = return_data(config)
    historical, _ = portfolio_volatility(returns,config["weights"],config["window"])
    pd.DataFrame([{"as_of":str(model["date"].date()),"model_annual_volatility":model_annual,
                   "historical_annual_volatility":historical,"factor_history_days":history_days}]).to_csv(output/"volatility.csv",index=False)
    print(f"Factor-model annualized volatility: {model_annual:.2%}")
    print(f"Historical annualized volatility: {historical:.2%}")
    rolling = portfolio.rolling(60,min_periods=60).std(ddof=1)*np.sqrt(252)
    fig, axes = plt.subplots(1,2,figsize=(12,4),gridspec_kw={"width_ratios":[2,1]})
    rolling.mul(100).plot(ax=axes[0],color="#2563eb",title="60-session rolling realized volatility")
    axes[0].set_ylabel("Annualized volatility (%)")
    axes[1].bar(["Factor model","Historical"],[model_annual*100,historical*100],color=["#2563eb","#93c5fd"])
    axes[1].set_ylabel("Annualized volatility (%)")
    axes[1].set_title(f"Current estimates | {model['date'].date()}")
    fig.tight_layout()
    fig.savefig(output/"volatility.png",dpi=150)
    plt.close(fig)
