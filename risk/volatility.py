"""Historical portfolio volatility from held-stock sample covariance."""
import numpy as np
import pandas as pd
from data import inputs, return_data
import matplotlib.pyplot as plt


def portfolio_volatility(returns, weights, window=252):
    history = returns.tail(window)
    if len(history) < window:
        raise ValueError(f"Need {window} complete daily returns")
    covariance = history.cov()
    w = pd.Series(weights).reindex(covariance.index)
    annual = float(np.sqrt(w @ covariance @ w * 252))
    return annual, covariance


if __name__ == "__main__":
    config, output = inputs()
    returns, portfolio = return_data(config)
    annual, covariance = portfolio_volatility(returns,config["weights"],config["window"])
    covariance.to_csv(output/"stock_covariance.csv")
    pd.DataFrame([{"as_of":str(portfolio.index[-1].date()),"historical_annual_volatility":annual,"window":config["window"]}]).to_csv(output/"volatility.csv",index=False)
    print(f"Historical annualized volatility: {annual:.2%}")
    rolling = portfolio.rolling(60,min_periods=60).std(ddof=1)*np.sqrt(252)
    ax = rolling.mul(100).plot(figsize=(9,4),color="#2563eb",title="60-session rolling realized volatility")
    ax.set_ylabel("Annualized volatility (%)")
    ax.figure.tight_layout()
    ax.figure.savefig(output/"volatility.png",dpi=150)
    plt.close(ax.figure)
