"""Eight style exposures relative to the current held stocks, not the market."""
import numpy as np
import pandas as pd
from data import inputs, build_panel
from factor import raw_factors
import matplotlib.pyplot as plt


def standardized_exposures(raw):
    """Use dates with complete eight-factor data for all held stocks."""
    n = raw.index.get_level_values("ticker").nunique()
    complete = raw.dropna().groupby(level="date").filter(lambda x:len(x)==n)
    return complete.groupby(level="date",group_keys=False).apply(lambda x:(x-x.mean())/x.std(ddof=0))


def fit_model(config):
    """OLS: today's returns on previous-session eight exposures plus intercept."""
    panel = build_panel(config)
    raw = raw_factors(panel)
    z = standardized_exposures(raw)
    calendar = panel.index.get_level_values("date").unique().sort_values()
    pairs = zip(calendar[:-1], calendar[1:])
    dates = set(z.index.get_level_values("date"))
    coefficients, residuals = [], []
    for previous, date in pairs:
        if previous not in dates:
            continue
        X = z.xs(previous).assign(market=1.)
        X = X[["market"]+list(z.columns)]
        y = panel.xs(date)["return"].reindex(X.index)
        coef = np.linalg.lstsq(X.to_numpy(),y.to_numpy(),rcond=None)[0]
        coefficients.append(pd.Series(coef,index=X.columns,name=date))
        residuals.append((y-X@coef).rename(date))
    date = panel.index.get_level_values("date").max()
    current = z.xs(date).reindex(config["weights"])
    return {"date":date,"raw":raw.xs(date).reindex(config["weights"]),"z":current,
            "factor_returns":pd.DataFrame(coefficients).sort_index(),
            "residuals":pd.DataFrame(residuals).sort_index()}


def exposures(config):
    model = fit_model(config)
    tilt = (model["z"].T @ pd.Series(config["weights"])).rename("portfolio_exposure")
    return model["date"], model["raw"], model["z"], tilt


if __name__ == "__main__":
    config, output = inputs()
    date, raw, z, tilt = exposures(config)
    raw.to_csv(output/"raw_exposures.csv")
    z.to_csv(output/"stock_exposures.csv")
    tilt.to_csv(output/"portfolio_exposures.csv")
    print(f"As of {date.date()}; reference = current holdings, not broad market")
    print(tilt.to_string(float_format=lambda x:f"{x:.4f}"))
    fig, axes = plt.subplots(1,2,figsize=(13,8),gridspec_kw={"width_ratios":[2,1]})
    image = axes[0].imshow(z,aspect="auto",cmap="RdBu_r",vmin=-3,vmax=3)
    axes[0].set_xticks(range(len(z.columns)),z.columns,rotation=45,ha="right")
    axes[0].set_yticks(range(len(z)),z.index)
    fig.colorbar(image,ax=axes[0],label="Holdings-relative Z-score")
    tilt.plot.barh(ax=axes[1],color="#2563eb")
    axes[1].axvline(0,color="grey",lw=.7)
    axes[1].set_title("Portfolio tilt relative to equal-weight holdings")
    fig.suptitle(f"Eight style exposures | {date.date()}")
    fig.tight_layout()
    fig.savefig(output/"exposures.png",dpi=150)
    plt.close(fig)
