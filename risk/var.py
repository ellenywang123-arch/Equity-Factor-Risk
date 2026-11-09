"""One-day empirical historical VaR of fixed-current-weight return shocks."""
import numpy as np


def sorted_losses(returns):
    """Finite observations only; preserve a negative loss threshold if all gains."""
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1 or len(r) < 2 or not np.isfinite(r).all():
        raise ValueError("Provide at least two finite portfolio returns")
    return np.sort(-r)


def historical_var(returns):
    """VaR is the inverse empirical loss CDF, in return units (0.01 = 1%)."""
    losses = sorted_losses(returns)
    index = min(int(np.ceil(0.95 * len(losses))) - 1, len(losses) - 1)
    return float(losses[index])


if __name__ == "__main__":
    from data import inputs, return_data
    import pandas as pd
    import matplotlib.pyplot as plt
    config, output = inputs()
    _, portfolio = return_data(config)
    history = portfolio.tail(config["window"])
    if len(history) < config["window"]:
        raise ValueError("Insufficient historical return window")
    value = historical_var(history)
    pd.DataFrame([{"as_of":str(history.index[-1].date()),"confidence":0.95,"var_1d":value}]).to_csv(output/"var.csv",index=False)
    print(f"One-day historical VaR (95%): {value:.2%}")
    fig, ax = plt.subplots(figsize=(9,4))
    ax.hist(-history*100,bins=35,color="#93c5fd")
    ax.axvline(value*100,color="#b45309",label=f"VaR 95% = {value:.2%}")
    ax.set(xlabel="One-day loss (%)",ylabel="Observations",title="Historical loss distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output/"var.png",dpi=150)
    plt.close(fig)
