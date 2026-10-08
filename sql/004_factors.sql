CREATE TABLE IF NOT EXISTS factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    category TEXT,
    description TEXT NOT NULL,
    inputs TEXT,
    impl_ref TEXT,
    frequency TEXT NOT NULL DEFAULT '1d',
    params TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);
