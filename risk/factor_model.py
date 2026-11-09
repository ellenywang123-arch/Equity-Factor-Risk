"""Eight style exposures relative to the current held stocks, not the market."""
import numpy as np
import pandas as pd
from data import inputs, build_panel
from factors import raw_factors
import matplotlib.pyplot as plt


def standardized_exposures(raw, minimum=15):
    """Daily Z-scores on complete held-stock observations; no extra universe."""
    sections = []
    for date, section in raw.groupby(level="date"):
        x = section.droplevel("date").dropna()
        if len(x) < minimum:
            continue
        scale = x.std(ddof=0)
        if (scale <= 1e-12).any():
            continue
        z = (x-x.mean())/scale
        z["date"] = date
        sections.append(z.reset_index().set_index(["date","ticker"]))
    if not sections:
        raise ValueError("Need at least 15 stocks with all eight styles on valid dates")
    return pd.concat(sections).sort_index()


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
        valid = y.notna()
        X, y = X.loc[valid], y.loc[valid]
        if len(X) < 15:
            continue
        coef, _, rank, _ = np.linalg.lstsq(X.to_numpy(), y.to_numpy(), rcond=None)
        if rank != X.shape[1]:
            continue
        coefficients.append(pd.Series(coef,index=X.columns,name=date))
        residuals.append((y-X@coef).rename(date))
    if len(coefficients) < 126:
        raise ValueError("Need at least 126 valid lagged cross-sectional regression days")
    date = panel.index.get_level_values("date").max()
    if date not in dates:
        raise ValueError("Latest date lacks enough complete style exposures")
    current = z.xs(date).reindex(config["weights"])
    if not np.isfinite(current.to_numpy()).all():
        raise ValueError("A current holding lacks a style; it will not be dropped")
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
    axes[1].set_title("Weighted tilt vs equal-weight holdings")
    fig.suptitle(f"Eight style exposures | {date.date()}")
    fig.tight_layout()
    fig.savefig(output/"exposures.png",dpi=150)
    plt.close(fig)
