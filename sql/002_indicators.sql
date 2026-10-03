-- 指标定义表

CREATE TABLE IF NOT EXISTS indicators (
    id INTEGER PRIMARY KEY,
    indicator_id TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    indicator_name TEXT NOT NULL,
    category TEXT NOT NULL,
    compute_ref TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    output_columns TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'deprecated', 'disabled')
    ),
    last_materialized_date TEXT,
    attach_kline INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (indicator_id, version),
    UNIQUE (storage_key)
);

CREATE INDEX IF NOT EXISTS idx_indicator_category_status
ON indicators (category, status);
