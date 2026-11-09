# Equity Portfolio Analytics

Twenty configured holdings, eight style exposures, factor-model and historical volatility, VaR/ES at **95%**, and simulated drawdown. Each risk module prints numbers and saves its own PNG/CSV. No main.py, report.py, HTML report, sector model, extra stock universe, tests folder or GitHub workflow.

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
                           ├─ risk/volatility.py → 模型／历史波动图和数值
                           ├─ risk/var.py → 95% VaR 图和数值
                           ├─ risk/expected_shortfall.py → 95% ES 图和数值
                           └─ risk/drawdown.py → 模拟净值／回撤图和数值
```

`risk/` 恰好五个 `.py`，Python 3 namespace package 不需要额外 `__init__.py`。`data.py` 只提供数据与共同命令参数，不充当总运行器。

## 二十只持仓：恢复八因子横截面风险模型

所有二十只股票既是持仓，也是回归样本，没有额外 universe，不使用 sector。每个交易日用上一交易日的八个风格暴露加共同截距解释当日收益：

$$
r_{i,t}=a_t+\sum_{k=1}^{8}z_{i,k,t-1}f_{k,t}+\varepsilon_{i,t}.
$$

满秩时，20条横截面观测估计9个参数，剩余自由度为11。历史日期允许部分财务数据不足，但至少需15只完整股票、且9列设计矩阵满秩；当前暴露则必须覆盖全部持仓。样本仍小，回归和残差估计不稳定，不能等同于机构级 Barra 模型。残差样本方差没有额外的横截面杠杆偏差修正，可能低估特有风险。

- 八因子图只显示持仓内标准化暴露，参照不是全市场。
- 波动率模块同时输出因子模型估计和直接历史协方差估计，分别命名。
- VaR/ES/Drawdown继续使用持仓历史收益，与因子模型是不同口径。

## 股票和配置

20只股票：AAPL、MSFT、GOOGL、AMZN、NVDA、META、AVGO、ORCL、CSCO、IBM、WMT、COST、KO、PEP、PG、JNJ、MRK、CAT、XOM、CVX。

AAPL、MSFT各10%；GOOGL、AMZN各8%；其余16只各4%，合计100%。这是人为设定的非等权演示组合，没有优化或投资推荐；非等权也让持仓相对自身等权基准的风格偏离更容易观察。公司覆盖科技／通信、消费、医疗、工业和能源，但仍偏大型公司，不代表全市场。

配置中只有 `weights`、`start`、`end`、`window=252`、`confidence=0.95`、`statement_lag_days=180`。

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
| `risk.factor_model.standardized_exposures(raw,minimum=15)` | 全历史原始指标 | 逐日完整案例 Z-score；跳过样本不足或零方差日期 |
| `risk.factor_model.fit_model(config)` | 二十只持仓数据 | 滞后暴露横截面OLS；输出最新暴露、因子收益和残差 |
| `risk.factor_model.exposures(config)` | fit_model结果及权重 | 输出日期、raw、当前Z-score、加权风格偏离 |
| `risk.volatility.portfolio_volatility(returns,weights,window)` | 最近252日股票收益 | 输出历史年化波动率、股票样本协方差 |
| `risk.volatility.model_volatility(model,weights,window)` | 因子收益、残差、当前暴露 | 样本F与对角D → 模型年化波动率和有效历史天数 |
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

逐日对具备全部八指标的实际持仓标准化，不额外截尾或中性化：

$$
z_{i,k}=\frac{x_{i,k}-\overline x_k}{s_k},\qquad
s_k=\sqrt{\frac1N\sum_i(x_{i,k}-\overline x_k)^2},\qquad
Exposure_k=\sum_iw_i z_{i,k}.
$$

历史日期若某列没有横截面差异或有效股票少于15则跳过；最新日期任何实际持仓缺少指标就报错，不静默删除持仓。正值为高于当前持仓平均，负值为低于平均。**不是相对全市场**；持仓改变会改变参照。所有持仓等权时，加权 Z-score 必然为0，所以这是相对同一批股票等权组合的风格偏离，不能据此判断绝对风险低。原始特征和各股标准化值也一起保存。

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

这等于同一窗口组合收益样本标准差乘 $\sqrt{252}$，是历史协方差估计。图中还展示60日滚动实现波动率。

因子模型使用最近最多252个有效回归日，至少126日。F为因子收益的样本协方差，D为每股残差样本方差组成的对角矩阵；每个持仓至少需126条有效残差，不补零：

$$
F=Cov(f_t),\quad d_i=Var(\varepsilon_{i,t}),\quad D=diag(d_i),\quad
b=X_{current}^{\top}w,\quad
\sigma_{model,ann}=\sqrt{252\left(b^{\top}Fb+\sum_iw_i^2d_i\right)}.
$$

当前X包含八风格及常数列；常数列在系数表中叫market，但它不是SPY收益，也不是额外估计的CAPM Beta。实际用 `np.linalg.lstsq` 逐日估计，不使用未来暴露解释当天收益；收益和暴露必须来自相邻交易日期。F采用简单样本协方差，不再使用Ledoit–Wolf收缩。

残差对角假设忽略个股残差间的共同波动，且没有行业控制；加上20只小样本与财务时点代理，预测需谨慎解释。年度缩放为常规近似。

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
| volatility | `volatility.png` | `volatility.csv`，含模型／历史两种估计 |
| var | `var.png` | `var.csv` |
| expected_shortfall | `es.png` | `es.csv` |
| drawdown | `drawdown.png` | `drawdown.csv`, `drawdown_summary.csv` |

没有 HTML、data checks 表、逐因子风险贡献图、行业分析或滚动校准报告。缺失持仓、错误权重、非有限收益等必要的报错保护保留在函数内部，避免输出错误数字。

## 数据限制

Yahoo 年报可能重述，180天假设不能建立严格的历史可用性。只有当前持仓，存在存续样本选择；股息、拆股和历史股数口径须核对。标准化暴露依赖持仓参照。原始数据与 outputs 留在本地，GitHub 仅放代码和派生图；数据使用遵守供应商条款。

## 当前缓存样例

截至2026-11-06，20只持仓全部具备当前八因子数据。模型年化波动率约12.83%、历史年化波动率约12.37%；一天95% VaR约1.28%、ES约1.71%；每日再平衡模拟路径最大回撤约−27.87%、当前回撤约−4.39%。模型有486个有效历史回归日，当前风险估计使用最近252个。不是实际投资业绩或未来风险保证。

![Holdings-relative exposures](examples/exposures.png)

![Simulated drawdown](examples/drawdown.png)
