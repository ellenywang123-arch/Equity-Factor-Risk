# Equity Factor Risk

An eight-style equity risk research project using Yahoo Finance inputs. Read the files in this order: **data.py → factors.py → risk.py → main.py → report.py**. No notebook, web service or database is required.

The model produces portfolio exposures, annualized volatility, market/sector/style variance contributions and specific-risk contributions. This is an MSCI-inspired educational implementation, not the proprietary MSCI/Barra model. It does not price derivatives or calculate VaR/ES.

## Verified example

The Yahoo run dated **2026-11-06** downloaded all 70 selected stocks; 65 had complete current eight-style coverage. The configured hypothetical nine-stock portfolio produced **16.35% model annualized volatility**, with **79.92% factor variance** and **20.08% specific variance**, using 252 historical factor-return observations.

![Illustrative variance contributions](examples/risk_contributions.png)

Past-only covariance calibration contains 278 daily observations (2025-10-01 to 2026-11-06). Realized squared returns / predicted variance is **0.423**: this diagnostic indicates substantial average overestimation of squared returns in this sample, not a successful forecast-accuracy claim. Financial timing, restatements, current sectors and selected-universe biases still apply. These numbers are research outputs, not a performance record or validated risk estimate. Five automated behavioural tests and the labelled synthetic end-to-end workflow also pass.

## Run in VS Code

Open this folder, create a Python 3.11+ environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --download
```

Open **outputs/report.html** in a browser. Subsequent runs use cached CSV files:

```powershell
.\.venv\Scripts\python.exe main.py
```

Edit `config.json` to change the stock universe, hypothetical portfolio weights or estimation window. Weights must sum to one; held stocks require complete exposures and enough residual history. Missing holdings never silently disappear. Yahoo may rate-limit requests; inspect `data/manifest.json` and retry when appropriate. The default selected universe excludes financial companies because a single ROE/book-equity definition is not uniformly appropriate across business models. It is a research sample, not historical index membership.

For an offline wiring check, using **clearly labelled synthetic inputs**, run:

```powershell
.\.venv\Scripts\python.exe main.py --synthetic --output outputs/synthetic
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Synthetic outputs do not establish market-data coverage, predictive accuracy or investment performance.

## Eight styles

| Style | Raw proxy |
| --- | --- |
| Value | Latest available-proxy annual common equity / market capitalization; positive equity required |
| Size | Log market capitalization |
| Momentum | Adjusted price at t−21 / adjusted price at t−252 − 1 |
| Volatility | 60-session sample return standard deviation × sqrt(252) |
| Quality | Latest annual common net income / average positive common equity |
| Yield | Trailing 365-calendar-day dividends / split-adjusted Close |
| Growth | Latest annual revenue year-over-year change |
| Liquidity | 60-session average share-turnover proxy |

These proxies implement the eight [MSCI style groups](https://www.msci.com/research-and-insights/blog-post/creating-a-common-language-for-factor-investing). Growth/ROE/income are **annual**, not quarterly or fully rolling TTM. Each day's complete-case cross-section is clipped at the 2.5/97.5 percentiles and standardized. No factor is mechanically neutralized against itself; sectors enter the regression explicitly. Optional orthogonalization and return-predictive IC screening are not used in this baseline risk model.

## Model

1. Download prices, annual statements, historical share counts and current sector labels. Cache raw CSV files locally with download status.
2. As-of join fundamentals to dates using an **assumed 180-calendar-day fiscal-end lag**. Never backfill before that proxy date; expire statements after 550 days.
3. Construct and standardize all eight exposures. Use the previous session's exposures to explain the next close-to-close return. Skip missing/gapped observations and rank-deficient regression dates.
4. Estimate daily cross-sectional returns with a common intercept, sector dummy contrasts (first alphabetic sector is reference), and eight style exposures. The intercept is a cross-sectional common return, not SPY's observed return. Regressions use ordinary least squares.
5. Over the most recent 252 eligible regression dates, estimate factor covariance F with Ledoit–Wolf and diagonal residual variance D. Require at least 126 residual observations for each held stock.
6. Compute Sigma = X F Xᵀ + D, portfolio exposure b = Xᵀw and daily variance bᵀ F b + Σ wᵢ²dᵢ.
7. Euler factor variance contribution is bₖ(Fb)ₖ. Specific contribution is wᵢ²dᵢ. Their sum equals total variance; contributions can be negative. Annual volatility contribution is daily variance contribution / daily portfolio volatility × sqrt(252).
8. Rolling validation fits F/D only on prior dates and compares predicted daily variance with the next realized squared fixed-weight return. Squared returns are noisy and include a mean component; aggregate calibration is a diagnostic, not a claim of forecast accuracy. No trading strategy or outperformance is claimed.

Market/sector contribution allocation depends on coding conventions. Ledoit–Wolf shrinkage is not invariant to arbitrary factor rescaling or sector reparameterization; interpret the decomposition only under the documented convention. A covariance estimator is not evidence that the economic model is complete.

## Outputs

- `report.html`, `risk_contributions.png`: readable report and contribution chart.
- `factor_contributions.csv`, `specific_contributions.csv`, `summary.json`: portfolio results.
- `exposures.csv`, `factor_returns.csv`, `factor_covariance.csv`, `specific_variance.csv`: model artifacts.
- `factor_coverage.csv`, `data_quality.csv`, `regression_quality.csv`: coverage and calculation checks.
- `rolling_validation.csv`: past-only risk calibration observations.

## Data limitations

Yahoo data is not a point-in-time fundamentals archive. A fiscal-end lag cannot prove actual publication availability or remove later restatements. Current sector labels and a surviving-stock universe create historical biases. Annual share-count coverage, splits, dividends and volume adjustments need vendor reconciliation. Historical capitalization and turnover are research proxies, not official Bloomberg fields. Missing-data attrition can alter the universe, and missing risk must not be replaced with zero. Do not present this as a validated institutional risk engine.

Yahoo/yfinance data is intended for permitted research/personal use under provider terms. Raw downloads and generated outputs are excluded from Git. No credentials are required. Share code and methodology rather than redistributing provider datasets.

## Attribution

The workflow is inspired by [KaniGAO/AlphaStream factors and risk](https://github.com/KaniGAO/AlphaStream). Elleny reports permission from the author to reuse the project. This version independently implements a compact Yahoo data layer, eight-style selection, lagged market/sector regressions, labelled Euler contributions and past-only validation, with AI-assisted development. It does not assert that the original repository is generally licensed for third-party reuse. The original project and its contributors retain their attribution.
