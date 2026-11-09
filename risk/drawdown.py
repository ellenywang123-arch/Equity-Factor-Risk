"""Fixed-weight daily-rebalanced illustrative NAV and drawdown, not a live record."""
import numpy as np
import pandas as pd


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


if __name__ == "__main__":
    from data import inputs, return_data
    import matplotlib.pyplot as plt
    config, output = inputs()
    _, returns = return_data(config)
    path = drawdown_series(returns)
    summary = drawdown_summary(path)
    path.to_csv(output/"drawdown.csv")
    pd.DataFrame([summary]).to_csv(output/"drawdown_summary.csv",index=False)
    print(f"Simulated daily-rebalanced current drawdown: {summary['current_drawdown']:.2%}")
    print(f"Maximum drawdown: {summary['max_drawdown']:.2%}")
    fig, axes = plt.subplots(2,1,figsize=(9,6),sharex=True)
    path.nav.plot(ax=axes[0],color="#2563eb",title="Hypothetical daily-rebalanced portfolio (no costs)")
    axes[0].set_ylabel("NAV (initial=1)")
    path.drawdown.mul(100).plot(ax=axes[1],color="#b45309")
    axes[1].set_ylabel("Drawdown (%)")
    fig.tight_layout()
    fig.savefig(output/"drawdown.png",dpi=150)
    plt.close(fig)
