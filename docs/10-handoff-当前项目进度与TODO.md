# 当前项目进度与 TODO Handoff

## 1. 文档目的

这份 handoff 基于当前仓库里的最新文档、代码和测试结果，给下一位接手者一个可以直接进入工作的项目快照。

它主要回答：

1. 当前项目做到哪一步了
2. 当前哪些设计已经落地
3. 下一步最应该做什么

## 2. 当前项目状态

当前项目已经从“纯文档阶段”进入“首版数据底座已收口、研究与回测尚未开始”的阶段。

更准确地说：

- 文档已经和当前代码实现对齐
- 数据接入侧已经有可以运行的 Python 实现
- 测试已经迁移到当前接口并全部通过
- 研究、回测、选股和运行侧模块仍然基本空白

一句话概括：

> 当前仓库已经有一套基于 Python + SQLite + AkShare 的本地离线数据接入底座，但还没有进入策略、回测和研究产物实现阶段。

## 3. 当前文档进度

## 3.1 已完成并与代码对齐的核心文档

- [01-量化交易系统概览](./01-量化交易系统概览.md)
- [02-饕餮系统架构设计](./02-饕餮系统架构设计.md)
- [03-A股市场适配说明](./03-A股市场适配说明.md)
- [04-分阶段落地路线图](./04-分阶段落地路线图.md)
- [05-数据模型设计](./05-数据模型设计.md)
- [06-数据接入与标准化存储方案](./06-数据接入与标准化存储方案.md)
- [07-策略接口与回测接口设计](./07-策略接口与回测接口设计.md)
- [08-首版数据接入与标准化存储详细设计](./08-首版数据接入与标准化存储详细设计.md)
- [09-FACTOR_SELECTION_MVP_CONCEPT](./09-FACTOR_SELECTION_MVP_CONCEPT.md)

其中最关键的变化是：

- `06` 和 `08` 已按当前代码实现收敛到 `AkShare + SQLite + 资源级 fetcher + 本地批处理` 这条真实链路
- 不再沿用旧版 `Tushare Pro / data_quality_issue / 通用 SourceAdapter / records.jsonl 默认落盘` 的设计口径

## 3.2 当前文档表达的真实边界

当前文档与代码统一后的事实是：

- 首版数据底座当前只正式覆盖 `stock`、`trading_calendar`、`daily_quote`、`ingestion_batch`
- 当前主数据源只有 `AkShare`
- 当前 Raw Layer 默认只写 `manifest.json`
- 当前还没有 `data_quality_issue` 正式表
- 当前 `daily_quote` 同步是“按股票增量续跑”，不是“按交易日抓全市场”

## 4. 当前代码进度

## 4.1 已落地能力

### 1) Python 项目骨架

当前项目已经具备最小可运行的 Python 工程结构：

- `modules/`
- `sql/`
- `pyproject.toml`
- `uv.lock`

### 2) SQLite 标准层

已落地：

- SQLite 连接封装
- schema 初始化器
- 首版 SQL 脚本 [sql/001_initial_schema.sql](../sql/001_initial_schema.sql)

当前正式表：

- `ingestion_batch`
- `stock`
- `trading_calendar`
- `daily_quote`

### 3) Repository 层

当前可用 repository：

- `BatchRepository`
- `StockRepository`
- `TradingCalendarRepository`
- `DailyQuoteRepository`
- `RepositorySession`

说明：

- 之前遗留的 `QualityIssueRepository` 导出已经移除
- 当前 repository 导出已经与仓库实际文件一致

### 4) 数据源 adapter

当前已实现：

- `AkshareStockAdapter`
- `AkshareTradingCalendarAdapter`
- `AkshareDailyQuoteAdapter`

当前 adapter factory：

- `create_stock_fetcher()`
- `create_trading_calendar_fetcher()`
- `create_stock_daily_quote_fetcher()`

### 5) 数据同步 pipeline

当前已实现：

- `StockPipeline`
- `TradingCalendarPipeline`
- `DailyQuotePipeline`

当前行为特征：

- `stock` 按全量快照同步
- `trading_calendar` 按自然日区间展开并写 `is_open`
- `daily_quote` 按股票从最新落库日期继续增量续跑

### 6) CLI job 入口

当前可用命令入口：

- `modules/datasource/jobs/sync_stocks.py`
- `modules/datasource/jobs/sync_trading_calendar.py`
- `modules/datasource/jobs/sync_daily_quotes.py`

## 4.2 尚未落地的部分

当前仍未开始或仅有占位的内容：

- 策略运行时
- 回测引擎
- 因子生成
- 未来标签定义
- 因子评估
- 选股规则沉淀
- 研究报告
- Serving Layer
- 风控 / 组合构建 / 订单 / 账户 / 实盘

`modules/engine/__init__.py` 当前仍为空，说明研究与回测主线尚未进入实现。

## 5. 当前实现的稳定事实

下一位接手者可以直接把下面这些当成当前事实，不需要再重复讨论：

- 当前程序化主数据源是 `AkShare`
- 当前标准层数据库是 SQLite
- 当前正式 schema 只有 `ingestion_batch / stock / trading_calendar / daily_quote`
- 当前 adapter 是“按资源拆协议”，不是统一 `fetch(request)` 总接口
- 当前 `daily_quote` 走“按股票增量续跑”
- 当前 Raw Layer 默认只有 `manifest.json`
- 当前测试基线已经以这些事实为准

## 6. 当前测试状态

当前已完成测试迁移，测试和当前实现接口已经对齐。

本次验证执行的是：

```bash
pytest -q
```

结果：

- `16 passed`

这意味着当前测试集已经不再依赖旧接口，例如：

- 不再依赖 `create_adapter`
- 不再依赖旧式 `Akshare*Adapter(..., client=...)` 构造协议
- 不再依赖旧的 `execute_stream()` / `iter_fetch_chunks()` 行为

## 7. 当前仍值得注意的限制

虽然测试已经通过，但这不代表数据底座已经“功能完整”。

当前还存在以下明确限制：

### 1) `request_params` 仍未完整记录

`ingestion_batch.request_params` 字段还在，但当前 pipeline 创建批次时仍写空字典。

这意味着批次追溯能力还不是最终版本。

### 2) `records.jsonl` 能力尚未接通主流程

当前 `RawStore.write_records_jsonl()` 已存在，但主流程默认只写 `manifest.json`。

这意味着 Raw Layer 还没有完全成为“原始证据层”。

### 3) `jobs/common.py` 仍有未收口辅助逻辑

这个文件不是当前测试主路径的一部分，但仍残留一些未完成的 helper 设计。

如果后续继续保留它，建议尽快做一次收口：

- 要么补齐其依赖的方法
- 要么把暂时不用的旧辅助逻辑删掉

### 4) `daily_quote` 仍是最简增量策略

当前实现只保证“能从最新已落库日期继续同步”，但还没有补：

- 历史缺口拦截
- 覆盖率告警
- 失败日期自动重刷

## 8. 下一步 TODO

当前决策已经明确，下一步直接进入研究与回测主线。 因此，接下来的默认 TODO 是：

## 8.1 进入研究与回测主线

基于当前已经收口的数据底座，优先继续以下工作：

1. 因子评估明细与回测/研究报告结构设计
2. 策略运行时实现
3. 回测引擎实现
4. `research_dataset_spec` 和 `backtest_result` 相关实现

当前数据层里那些未补强项，例如：

- `request_params` 仍为空
- `records.jsonl` 未接入主流程
- `jobs/common.py` 仍有未收口 helper
- `daily_quote` 仍没有缺口告警与覆盖率能力

先视为已接受的当前边界，而不是下一步默认阻塞项。

## 9. 推荐起手式

如果下一位接手者想最快进入有效工作，我建议按这个顺序：

1. 先读 [06-数据接入与标准化存储方案](./06-数据接入与标准化存储方案.md) 和 [08-首版数据接入与标准化存储详细设计](./08-首版数据接入与标准化存储详细设计.md)
2. 再读 `modules/datasource/` 和 `modules/repositories/`
3. 直接补 `因子评估明细与回测/研究报告结构设计`
4. 开始实现策略运行时
5. 再实现回测引擎与结果产物

## 10. 当前结论

当前仓库已经不再处于“设计远多于实现”的最早阶段。

更准确的描述是：

> 首版数据接入底座已经有一套文档、代码和测试都对齐的最小可用实现；当前决策是接受这套数据层边界，下一阶段直接进入研究、选股与回测模块实现。
