"""One-day historical ES with exact probability mass at the empirical boundary."""
import numpy as np
from .var import sorted_losses


def historical_es(returns):
    """Average worst 5% mass, fractionally weighting the boundary."""
    descending = sorted_losses(returns)[::-1]
    mass = 0.05 * len(descending)
    whole = int(np.floor(mass))
    fraction = mass - whole
    total = descending[:whole].sum()
    if fraction > 0 and whole < len(descending):
        total += fraction * descending[whole]
    return float(total / mass)


if __name__ == "__main__":
    from data import inputs, return_data
    from .var import historical_var
    import pandas as pd
    import matplotlib.pyplot as plt
    config, output = inputs()
    _, portfolio = return_data(config)
    history = portfolio.tail(config["window"])
    if len(history) < config["window"]:
        raise ValueError("Insufficient historical return window")
    value, threshold = historical_es(history), historical_var(history)
    pd.DataFrame([{"as_of":str(history.index[-1].date()),"confidence":0.95,"es_1d":value}]).to_csv(output/"es.csv",index=False)
    print(f"One-day historical ES (95%): {value:.2%}")
    fig, ax = plt.subplots(figsize=(9,4))
    ax.hist(-history*100,bins=35,color="#93c5fd")
    ax.axvline(threshold*100,color="grey",linestyle="--",label="VaR 95%")
    ax.axvline(value*100,color="#b45309",label=f"ES 95% = {value:.2%}")
    ax.set(xlabel="One-day loss (%)",ylabel="Observations",title="Average loss in the worst 5% probability tail")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output/"es.png",dpi=150)
    plt.close(fig)
