# Equity Portfolio Analytics

Nine configured holdings, eight style exposures, historical volatility, VaR/ES at **95%**, and simulated drawdown. Each risk module prints numbers and saves its own PNG/CSV. No main.py, report.py, HTML report, sector model, extra stock universe, tests folder or GitHub workflow.

## 运行

在 VS Code 打开整个文件夹，选择项目 Python 3.11+ 环境。首次安装：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

首次下载只获取 `config.json` 的持仓股票：

```powershell
.\.venv\Scripts\python.exe -m risk.factor_model --download
```

之后分别运行所需模块，默认使用本地缓存：

```powershell
.\.venv\Scripts\python.exe -m risk.factor_model
.\.venv\Scripts\python.exe -m risk.volatility
.\.venv\Scripts\python.exe -m risk.var
.\.venv\Scripts\python.exe -m risk.expected_shortfall
.\.venv\Scripts\python.exe -m risk.drawdown
```

每个命令可加 `--config path.json` 或 `--download`。在项目根目录使用 `-m`，不要单独双击子文件。PNG 和 CSV 在 `outputs/`。没有统一报告步骤；无图形窗口的环境也能保存图。

## 架构与 Input → Output

```text
config.json: weights 即全部股票，没有额外 universe
          ↓
data.py: Yahoo 下载 / 本地缓存
          ├─ 年报 + 股数 + 价格 → factors.py → risk/factor_model.py → 八因子暴露图和数值
          └─ 持仓价格 → return_data()
                           ├─ risk/volatility.py → 历史波动图和数值
                           ├─ risk/var.py → 95% VaR 图和数值
                           ├─ risk/expected_shortfall.py → 95% ES 图和数值
                           └─ risk/drawdown.py → 模拟净值／回撤图和数值
```

`risk/` 恰好五个 `.py`，Python 3 namespace package 不需要额外 `__init__.py`。`data.py` 只提供数据与共同命令参数，不充当总运行器。

## 为什么不再做八因子横截面风险回归？

当前只有九只持仓。如果对九只股票回归八因子加截距，满秩时会完全拟合，不能可靠估计个股残差。于是此版本明确分开：

- **八因子：** 描述当前持仓的相对风格特征；没有因子收益、行业项、逐因子方差贡献或 Barra 风险预测。
- **组合波动率：** 使用持仓收益的历史样本协方差，完全不依赖因子暴露。
- **VaR / ES / Drawdown：** 使用同一组持仓的历史收益。

这是根据持仓规模作的模型调整，不能把新波动率叫成原来的 Barra-style 模型波动率，或把风格得分叫做收益回归 Beta。

## 股票和配置

AAPL、MSFT 各 15%；GOOGL、AMZN、WMT、KO、JNJ、CAT、XOM 各 10%。它们只是便于演示的模拟组合，没有选股优化或投资推荐。配置中只有 `weights`、`start`、`end`、`window=252`、`confidence=0.95`、`statement_lag_days=180`。

修改 weights 就同时修改下载列表、计算范围和暴露参照，不需维护另一份股票池。权重须为非负有限值、合计 1。缓存刷新失败不会删除旧文件，请留意下载状态和价格日期。

## 每个函数做什么

| 文件 / 函数 | Input | 处理与 Output |
| --- | --- | --- |
| `data.inputs()` | 命令行、JSON | 读取配置、必要参数保护，可选下载，返回 config 和 outputs 路径 |
| `data.clean_dates(frame)` | 日期索引表 | 去时区、归一日期、同日保留最后记录、排序 |
| `data.download(config)` | weights 中的股票 | Yahoo 行情、年报、股数 → 本地 CSV；失败持仓不静默剔除 |
| `data.statement_row(frame,name)` | 年报及科目名 | 提取并按日期排序；缺失返回空 Series |
| `data.annual_metrics(income,balance,lag)` | 两张年报 | 年度 ROE、收入同比和权益，索引为假设可用日 |
| `data.build_panel(config)` | 持仓缓存 | 向后匹配财务、股数及价格，输出 date/ticker panel；无 sector、无审计报告 |
| `data.return_data(config)` | 仅持仓价格缓存 | 输出股票收益宽表和组合收益 Series；不需要年报 |
| `factors.raw_factors(panel)` | panel | 逐只股票计算八个原始特征，避免 rolling 混股 |
| `risk.factor_model.exposures(config)` | 最新八特征和权重 | 输出日期、raw、持仓内 Z-score、加权风格偏离 |
| `risk.volatility.portfolio_volatility(returns,weights,window)` | 最近252日股票收益 | 输出历史年化波动率、股票样本协方差 |
| `risk.var.sorted_losses(returns)` | 有限的一维组合收益 | 损失取负并升序排列 |
| `risk.var.historical_var(returns)` | 历史组合收益 | 95% 经验损失分位数 |
| `risk.expected_shortfall.historical_es(returns)` | 同样的历史收益 | 最坏5%概率区间的平均损失，边界按比例计入 |
| `risk.drawdown.drawdown_series(returns)` | 全部共同有效持仓收益 | 输出简单收益、模拟NAV、回撤 |
| `risk.drawdown.drawdown_summary(path)` | NAV路径 | 当前／最大回撤、起止日和观测数 |

每个 `risk/*.py` 的 `if __name__ == "__main__"` 读取数据、调用自己的函数、打印数字并保存自己的图表。导入模块不会自动启动计算。

## 八因子公式与参照范围

设调整后价格为 $A$，Yahoo Close 为 $C$，拆股基准匹配后的股数为 $Q^{adj}$，市值代理 $MC=CQ^{adj}$；最新可用代理财年的普通股权益为 $B_y$、净利润为 $NI_y$、收入为 $Rev_y$。

| 因子 | 公式 |
| --- | --- |
| Value | $B_y/MC_t$ |
| Size | $\ln MC_t$ |
| Momentum | $A_{t-21}/A_{t-252}-1$ |
| Volatility | $s(r_{t-59:t})\sqrt{252}$ |
| Quality | $NI_y/[(B_y+B_{y-1})/2]$ |
| Yield | $\sum_{u\in(t-365d,t]}Dividend_u/C_t$ |
| Growth | $Rev_y/Rev_{y-1}-1$ |
| Liquidity | $\frac1{60}\sum_{u=t-59}^t Volume_u/Q^{adj}_u$ |

八组名称参考 [MSCI 风格分类](https://www.msci.com/research-and-insights/blog-post/creating-a-common-language-for-factor-investing)，指标是本项目的简单代理。年报只在财年结束后假设180天才使用，超过代理可用日550天不用；不是实际公告时点，也不是完整滚动 TTM。ROE 要求两期正权益。股票分红、股数、价格和成交量的调整基准仍需核对。

只对最新日期、全部实际持仓做标准化，不额外截尾或中性化：

$$
z_{i,k}=\frac{x_{i,k}-\overline x_k}{s_k},\qquad
s_k=\sqrt{\frac1N\sum_i(x_{i,k}-\overline x_k)^2},\qquad
Exposure_k=\sum_iw_i z_{i,k}.
$$

若某特征在所有持仓完全相同，设该列相对暴露为0；真实缺失则报错，不剔除股票。正值为高于当前持仓平均，负值为低于平均。**不是相对全市场**；持仓改变会改变参照。所有持仓等权时，加权 Z-score 必然为0，所以这是相对同一批股票等权组合的风格偏离，不能据此判断绝对风险低。原始特征和各股标准化值也一起保存。

## 收益和波动率

从调整后价格计算简单收益并加权：

$$
r_{i,t}=\frac{A_{i,t}}{A_{i,t-1}}-1,\qquad r_{p,t}=\sum_iw_i r_{i,t}.
$$

从首个所有持仓都有收益的日期开始；之后有内部缺失则停止，不补零、不重新分配权重。股票只下载一次，后续四个风险模块都只需要价格。

最近252日样本协方差与组合年化波动：

$$
S_{ij}=\frac1{T-1}\sum_t(r_{i,t}-\overline r_i)(r_{j,t}-\overline r_j),\qquad
\sigma_{p,ann}=\sqrt{252\,w^\top S w}.
$$

这等于同一窗口组合收益样本标准差乘 $\sqrt{252}$，不是因子模型预测。图中展示60日滚动实现波动率；年度缩放采用常规近似。

## VaR 与 ES：仅95%，一个交易日

最近252条持仓收益转成损失 $L_t=-r_{p,t}$；正数表示亏损，负数表示盈利。95% VaR 用经验分布反函数：

$$
VaR_{0.95}=L_{(\lceil0.95n\rceil)}.
$$

ES 平均最坏5%概率质量。降序损失为 $L_{[1]}\ge\cdots\ge L_{[n]}$，令 $m=0.05n,q=\lfloor m\rfloor,a=m-q$：

$$
ES_{0.95}=\frac{\sum_{j=1}^{q}L_{[j]}+aL_{[q+1]}}{m}.
$$

252条数据的5%等效为12.6条，所以内部取最坏12条，加第13条的0.6份。这就是之前 `tail probability mass` 的意思；**输出已删除这个字段**，但计算保留正确的分数边界。若 a=0，边界项为零。收益比例0.01表示1%；不计算99%、不作多日平方根缩放、不强行将负结果截零。两者都不是最大损失保证。

## Drawdown

对全历史、固定每日权重复利：

$$
NAV_t=\prod_{s\le t}(1+r_{p,s}),\qquad
H_t=\max(1,NAV_1,\ldots,NAV_t),\qquad
DD_t=\frac{NAV_t}{H_t}-1,\qquad MDD=\min_tDD_t.
$$

初始 NAV=1 包含在高点内，首日下跌也会计入回撤。负数表示下降。路径代表每日再平衡模拟，不是固定股数持有，无费用、税或滑点，不是实际业绩。VaR/ES窗口是近252日，回撤窗口是全部共同有效历史，含义不同。

## 输出

| 模块 | 图 | 数字文件 |
| --- | --- | --- |
| factor_model | `exposures.png` | `raw_exposures.csv`, `stock_exposures.csv`, `portfolio_exposures.csv` |
| volatility | `volatility.png` | `volatility.csv`, `stock_covariance.csv` |
| var | `var.png` | `var.csv` |
| expected_shortfall | `es.png` | `es.csv` |
| drawdown | `drawdown.png` | `drawdown.csv`, `drawdown_summary.csv` |

没有 HTML、data checks 表、因子风险贡献、行业分析或滚动校准报告。缺失持仓、错误权重、非有限收益等必要的报错保护保留在函数内部，避免输出错误数字。

## 数据限制

Yahoo 年报可能重述，180天假设不能建立严格的历史可用性。只有当前持仓，存在存续样本选择；股息、拆股和历史股数口径须核对。标准化暴露依赖持仓参照。原始数据与 outputs 留在本地，GitHub 仅放代码和派生图；数据使用遵守供应商条款。

## 当前缓存样例

截至2026-11-06、近252日：历史年化波动率11.67%，一天95% VaR约1.06%、ES约1.48%。2020-01-03起的每日再平衡模拟路径最大回撤约−28.10%，当前回撤约−3.65%。不是实际投资业绩或未来风险保证。

![Holdings-relative exposures](examples/exposures.png)

![Simulated drawdown](examples/drawdown.png)
