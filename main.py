"""Run: python main.py --download; offline software check: python main.py --synthetic."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from data import download,build_panel
from factors import raw_factors,standardize
from risk import regress,covariance,portfolio_risk,rolling_validation
from report import save_report


def synthetic_panel():
    """Seeded fixtures test wiring only; never label as downloaded market data."""
    rng=np.random.default_rng(17)
    dates=pd.bdate_range("2021-01-01",periods=750)
    market=rng.normal(0,.01,len(dates))
    frames=[]
    for i in range(70):
        r=market*rng.uniform(.5,1.6)+rng.normal(0,rng.uniform(.008,.025),len(dates))
        price=100*np.cumprod(1+r)
        cap=price*rng.uniform(1e7,1e9)
        p=pd.DataFrame({"adjusted_price":price,"market_cap":cap,"return":r,"market_return":market,"equity":rng.uniform(.1,1)*cap[0],"roe":rng.uniform(.02,.4),"growth":rng.uniform(-.1,.4),"dividend_yield":rng.uniform(0,.06),"turnover":rng.uniform(.001,.05,len(dates)),"sector":f"Sector{i%5}","ticker":f"S{i:02}"},index=dates)
        frames.append(p)
    return pd.concat(frames).rename_axis("date").reset_index().set_index(["date","ticker"]).sort_index()


def run(config,output="outputs",data_dir="data",synthetic=False,validate=False):
    out=Path(output)
    out.mkdir(parents=True,exist_ok=True)
    if synthetic:
        panel=synthetic_panel()
        config={**config,"weights":{f"S{i:02}":.1 for i in range(10)}}
        audit=pd.DataFrame([{"status":"synthetic fixture; no Yahoo data used"}])
    else:
        panel,audit=build_panel(config,data_dir)
    audit.to_csv(out/"data_quality.csv",index=False)
    raw=raw_factors(panel)
    coverage=raw.groupby(level="date").count()
    coverage.to_csv(out/"factor_coverage.csv")
    x=standardize(raw,config["min_stocks"])
    f,eps,ranks,design=regress(x,panel,config["min_stocks"])
    ranks.to_csv(out/"regression_quality.csv",index=False)
    as_of=x.index.get_level_values("date").max()
    latest_panel_date=panel.index.get_level_values("date").max()
    if (latest_panel_date-as_of).days>7:
        raise ValueError(f"Latest usable exposure is stale: {as_of}; latest market data: {latest_panel_date}")
    history=f.loc[f.index<=as_of].tail(config["risk_window"])
    F,D,shrinkage=covariance(history,eps.reindex(history.index),config["min_history"])
    current=design.xs(as_of).copy()
    # Forecast from today's close uses today's style exposures, not yesterday's.
    current.loc[:,x.columns]=x.xs(as_of).reindex(current.index)
    summary,contributions,specific=portfolio_risk(current,F,D,config["weights"])
    summary["covariance_shrinkage"]=shrinkage
    summary["history_days"]=len(history)
    if validate:
        validation=rolling_validation(f,eps,design,panel,config["weights"],config["risk_window"],config["min_history"])
        validation.to_csv(out/"rolling_validation.csv",index=False)
    x.to_csv(out/"exposures.csv")
    f.to_csv(out/"factor_returns.csv")
    F.to_csv(out/"factor_covariance.csv")
    D.rename("daily_specific_variance").to_csv(out/"specific_variance.csv")
    save_report(out,summary,contributions,specific,audit,config,as_of,synthetic)
    print(json.dumps({"as_of":str(as_of),"synthetic":synthetic,**summary},indent=2))
    print(f"Open {out.resolve() / 'report.html'}")
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config.json")
    parser.add_argument("--data",default="data")
    parser.add_argument("--output",default="outputs")
    parser.add_argument("--download",action="store_true")
    parser.add_argument("--synthetic",action="store_true")
    parser.add_argument("--validate",action="store_true",help="Save optional past-only calibration to CSV; never shown in the HTML report")
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    if args.download and args.synthetic:
        parser.error("Choose Yahoo download or synthetic fixtures")
    if args.download:
        download(config,args.data)
    run(config,args.output,args.data,args.synthetic,args.validate)
