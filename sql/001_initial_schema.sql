PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS ingestion_batch (
    id INTEGER PRIMARY KEY,
    batch_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    resource_type TEXT NOT NULL CHECK (resource_type IN ('stock', 'trading_calendar', 'daily_quote')),
    sync_mode TEXT NOT NULL CHECK (sync_mode IN ('full', 'incremental', 'refresh')),
    start_date TEXT,
    end_date TEXT,
    request_params TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    raw_count INTEGER NOT NULL DEFAULT 0,
    valid_count INTEGER NOT NULL DEFAULT 0,
    loaded_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ingestion_batch_resource_started
ON ingestion_batch (resource_type, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_batch_status_started
ON ingestion_batch (status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_batch_resource_sync_trade_date
ON ingestion_batch (resource_type, sync_mode);

CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY,
    market TEXT NOT NULL,
    exchange TEXT NOT NULL CHECK (exchange IN ('SSE', 'SZSE')),
    symbol TEXT NOT NULL,
    ticker TEXT,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type = 'stock'),
    currency TEXT NOT NULL CHECK (currency = 'CNY'),
    lot_size INTEGER NOT NULL CHECK (lot_size > 0),
    listed_at TEXT,
    delisted_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'delisted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (market, exchange, symbol),
    CHECK (delisted_at IS NULL OR listed_at IS NULL OR listed_at <= delisted_at)
);

CREATE INDEX IF NOT EXISTS idx_stock_status_exchange
ON stock (status, exchange);

CREATE INDEX IF NOT EXISTS idx_stock_updated_at
ON stock (updated_at DESC);

CREATE TABLE IF NOT EXISTS trading_calendar (
    id INTEGER PRIMARY KEY,
    market TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    is_open INTEGER NOT NULL CHECK (is_open IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (market, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_trading_calendar_trade_date
ON trading_calendar (trade_date DESC);

CREATE TABLE IF NOT EXISTS daily_quote (
    id INTEGER PRIMARY KEY,
    stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open INTEGER NOT NULL CHECK (open > 0),
    high INTEGER NOT NULL CHECK (high > 0),
    low INTEGER NOT NULL CHECK (low > 0),
    close INTEGER NOT NULL CHECK (close > 0),
    volume INTEGER NOT NULL CHECK (volume >= 0),
    turnover INTEGER CHECK (turnover IS NULL OR turnover >= 0),
    ingestion_batch_id INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (stock_id, trade_date),
    FOREIGN KEY (stock_id) REFERENCES stock(id),
    FOREIGN KEY (ingestion_batch_id) REFERENCES ingestion_batch(id),
    CHECK (high >= open),
    CHECK (high >= close),
    CHECK (low <= open),
    CHECK (low <= close),
    CHECK (high >= low)
);

CREATE INDEX IF NOT EXISTS idx_daily_quote_trade_date_stock
ON daily_quote (trade_date, stock_id);

CREATE INDEX IF NOT EXISTS idx_daily_quote_ingestion_batch
ON daily_quote (ingestion_batch_id);
