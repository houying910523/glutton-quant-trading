CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    strategy_params TEXT NOT NULL DEFAULT '{}',
    config TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed')),
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    analysis_json TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_status_created
ON backtest_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy_created
ON backtest_runs (strategy_id, created_at DESC);
