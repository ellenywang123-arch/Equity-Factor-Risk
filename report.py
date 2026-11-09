"""Save CSVs, charts and a self-contained HTML report; no web backend."""
from html import escape
from pathlib import Path
import base64
import io
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def save_report(output, summary, contributions, specific, audit, validation, config, as_of, synthetic=False):
    out=Path(output)
    out.mkdir(parents=True,exist_ok=True)
    contributions.to_csv(out/"factor_contributions.csv")
    specific.rename("daily_variance_contribution").to_csv(out/"specific_contributions.csv")
    audit.to_csv(out/"data_quality.csv",index=False)
    validation.to_csv(out/"rolling_validation.csv",index=False)
    (out/"summary.json").write_text(json.dumps({"as_of":str(as_of),"synthetic":synthetic,**summary,"config":config},indent=2),encoding="utf-8")
    fig,ax=plt.subplots(figsize=(10,5))
    chart=contributions.total_variance_share.copy()
    chart.loc["Specific (all stocks)"]=summary["specific_variance_share"]
    chart.mul(100).plot.barh(ax=ax,color=["#b45309" if v<0 else "#2563eb" for v in chart])
    ax.set_xlabel("Contribution to total variance (%)")
    ax.set_title(f"{'Synthetic check' if synthetic else 'Yahoo research prototype'} | {str(as_of)[:10]}")
    ax.axvline(0,color="grey",lw=.7)
    fig.tight_layout()
    fig.savefig(out/"risk_contributions.png",dpi=150)
    buffer=io.BytesIO()
    fig.savefig(buffer,format="png",dpi=130)
    plt.close(fig)
    picture=base64.b64encode(buffer.getvalue()).decode()
    calibration="No eligible rolling observations."
    if not validation.empty:
        ratio=validation.realized_squared_return.sum()/validation.predicted_daily_variance.sum()
        calibration=f"Past-only rolling validation: {len(validation)} daily observations. Realized squared returns / predicted variance = {ratio:.3f}. This is a noisy aggregate calibration diagnostic, not a volatility forecast accuracy score."
    status="SYNTHETIC SOFTWARE CHECK — NOT MARKET RESULTS" if synthetic else "YAHOO RESEARCH PROTOTYPE — APPROXIMATE FUNDAMENTAL TIMING"
    html=f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Equity Factor Risk</title>
    <style>body{{font:16px system-ui;max-width:1050px;margin:40px auto;padding:0 24px;background:#fafbfe;color:#172033}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}img{{width:100%}}.status{{color:#92400e}}p{{line-height:1.6}}</style>
    <h1>Equity Factor Risk</h1><p class="status">{status}</p><p>As of {escape(str(as_of))}. Hypothetical fixed holdings.</p>
    <h2>Annualized model volatility: {summary['annual_volatility']:.1%}</h2>
    <p>Factor variance share: {summary['factor_variance_share']:.1%}; specific variance share: {summary['specific_variance_share']:.1%}.</p>
    <img alt="Risk contribution breakdown" src="data:image/png;base64,{picture}">
    <h2>Exposure and Euler contributions</h2>{contributions.to_html(float_format=lambda x:f'{x:.5f}')}<p>Eight style factors plus a market intercept and sector contrasts. Negative contributions indicate diversification under this decomposition. Sector/market allocation depends on the reference-sector convention; total variance is the main invariant.</p>
    <h2>Validation</h2><p>{calibration}</p>
    <h2>Data checks</h2>{audit.to_html(index=False)}
    <h2>Method and limits</h2><p>Daily lagged cross-sectional regression; Ledoit–Wolf factor covariance; diagonal residual variance; 252-session annualization. Financials are annual, potentially restated, and made available with an assumed {config['statement_lag_days']}-day fiscal-end lag. This does not establish point-in-time validity. Current sector classifications and a selected surviving-stock universe introduce historical bias. Yahoo share/dividend/volume adjustments require independent reconciliation. The report is not official MSCI/Barra output, investment advice, VaR or ES.</p></html>"""
    (out/"report.html").write_text(html,encoding="utf-8")
