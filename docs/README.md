# 饕餮文档索引

`docs/` 只保留正式文档；其中一部分是目标架构/路线图，一部分是基于当前代码收口后的实现文档。

## 推荐阅读顺序

1. [01-量化交易系统概览](./01-量化交易系统概览.md)
2. [02-饕餮系统架构设计](./02-饕餮系统架构设计.md)
3. [03-A股市场适配说明](./03-A股市场适配说明.md)
4. [04-分阶段落地路线图](./04-分阶段落地路线图.md)
5. [05-数据模型设计](./05-数据模型设计.md)
6. [06-数据接入与标准化存储方案](./06-数据接入与标准化存储方案.md)
7. [07-指标计算存储与查询实施方案](./07-指标计算存储与查询实施方案.md)
8. [08-因子研究与选股系统 MVP 概念设计](./08-FACTOR_SELECTION_MVP_CONCEPT.md)
9. [09-策略接口与回测接口设计](./09-策略接口与回测接口设计.md)
10. [10-水平箱体过滤器改造设计](./10-水平箱体过滤器改造设计.md)
11. [11-沪深主板过滤器设计](./11-沪深主板过滤器设计.md)
12. [12-策略单时点决策与运行控制](./12-策略单时点决策与运行控制.md)
13. [13-回测引擎与结果分析模块设计](./13-回测引擎与结果分析模块设计.md)

## 各文档职责

- `01`：建立系统全貌和术语认知
- `02`：定义目标架构和 MVP 边界
- `03`：集中说明 A 股约束，以及当前代码已经固定下来的 A 股口径
- `04`：说明项目应按什么阶段推进，以及结合现状的下一步建议
- `05`：以当前 `sql/` 和 `modules/repositories/models.py` 为准，整理真实数据模型
- `06`：当前数据接入、标准层落库、HTTP/CLI 入口的实现边界
- `07`：当前指标定义、Parquet 物化、DuckDB 查询的实现方案
- `08`：研究方法论视角下的因子/标签/评估/选股概念设计
- `09`：当前 `Factor` / `Filter` / `Strategy` / `Backtest` 的真实代码边界
- `10`：水平箱体过滤器当前实现说明
- `11`：沪深主板过滤器当前实现说明
- `12`：当前策略单时点决策与运行控制边界
- `13`：回测引擎与结果分析模块的当前骨架设计

## 当前代码状态摘要

基于当前仓库，已经明确落地的主线是：

- FastAPI 运行时与控制器装配：`modules/app.py`、`modules/controller/`
- AkShare 数据接入与 SQLite 标准层：`stock_info`、`trading_calendar`、`stock_daily`
- 数据同步 pipeline 与 Typer 脚本：`modules/datasource/pipeline/`、`modules/datasource/scripts/`
- 指标定义管理、内置指标、Parquet 分区物化：`modules/indicators/`
- 基于 DuckDB 的指标查询拼接：`modules/indicators/indicator_service.py`
- 研究侧筛选链路：`Filter`、`Selection`、`main_board` / `turnover_rate` / `box_consolidation`
- 策略原型：`BuyAndHoldStrategy`、`FactorScoreStrategy`
- 回测最小闭环：`modules/backtest/models.py`、`scheduler.py`、`engine.py`、`market_data.py`、`order_builder.py`、`execution.py`、`valuation.py`、`trade_ledger.py`、`analyzer.py`、`runner.py`

仍处于占位、半成品或待补齐阶段的主线是：

- 回测层更完整的交易闭合边界、停牌处理、涨跌停细化等 A 股执行约束
- `factors` / `strategies` SQL 表对应的 repository 与服务层
- 更完整的研究评估、标签、报告与回测结果模型
- 实盘执行、订单、账户、风控与调度

## 当前结论

- 当前最稳定的代码边界已经不只是“数据接入”，而是“数据接入 + 标准层 + 指标物化/查询 + 研究筛选原型”
- 回测层已经补出输入输出模型、调仓日调度器、分析器、runner、同步回测 API，以及 `BacktestEngine.run()` 的最小执行流：固定调仓、`strategy.decide()`、`next_open` 成交、收盘估值、净值曲线、订单/成交/基础闭合交易记录，并已加入 A 股 `T+1`、整手买入和普通沪深 A 股 10% 涨跌停的保守约束
- 文档中凡是涉及表名、模块名、函数签名、已实现能力时，应以 `modules/` 与 `sql/` 的现状为准
