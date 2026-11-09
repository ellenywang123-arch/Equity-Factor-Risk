"""Eight style exposures relative to the current held stocks, not the market."""
import numpy as np
import pandas as pd
from data import inputs, build_panel
from factors import raw_factors
import matplotlib.pyplot as plt


def exposures(config):
    panel = build_panel(config)
    raw = raw_factors(panel)
    date = raw.index.get_level_values("date").max()
    current = raw.xs(date).reindex(config["weights"])
    if not np.isfinite(current.to_numpy()).all():
        raise ValueError("A held stock lacks a current factor; do not silently omit it")
    if len(current) < 2:
        raise ValueError("Need at least two holdings for relative exposures")
    scale = current.std(ddof=0)
    # A constant characteristic cannot distinguish these holdings: assign zero tilt.
    z = (current-current.mean()).div(scale.replace(0, np.nan)).fillna(0)
    tilt = (z.T @ pd.Series(config["weights"])).rename("portfolio_exposure")
    return date, current, z, tilt


if __name__ == "__main__":
    config, output = inputs()
    date, raw, z, tilt = exposures(config)
    raw.to_csv(output/"raw_exposures.csv")
    z.to_csv(output/"stock_exposures.csv")
    tilt.to_csv(output/"portfolio_exposures.csv")
    print(f"As of {date.date()}; reference = current holdings, not broad market")
    print(tilt.to_string(float_format=lambda x:f"{x:.4f}"))
    fig, axes = plt.subplots(1,2,figsize=(12,5),gridspec_kw={"width_ratios":[2,1]})
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
