CREATE TABLE IF NOT EXISTS factor_definition (
    id INTEGER PRIMARY KEY,
    factor_id TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    factor_name TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (factor_id, version),
    UNIQUE (storage_key)
);

CREATE INDEX IF NOT EXISTS idx_factor_definition_category_status
ON factor_definition (category, status);
