INSERT INTO factor_definition (
    factor_id,
    version,
    factor_name,
    category,
    compute_ref,
    params,
    output_columns,
    storage_key,
    description,
    status,
    created_at,
    updated_at
) VALUES (
    'ma_5_10_20_30_60_120',
    'v1',
    '5/10/20/30/60/120均线',
    'trend',
    'modules.factors.builtin.trend:SimpleMovingAverageFactor',
    '{"window":[5,10,20,30,60,120]}',
    '["ma_5","ma_10","ma_20","ma_30","ma_60","ma_120"]',
    'ma/v1/window',
    '默认内置 5/10/20/30/60/120 日均线因子定义',
    'active',
    '2025-01-01 00:00:00',
    '2025-01-01 00:00:00'
)
ON CONFLICT(factor_id, version) DO UPDATE SET
    factor_name = excluded.factor_name,
    category = excluded.category,
    compute_ref = excluded.compute_ref,
    params = excluded.params,
    output_columns = excluded.output_columns,
    storage_key = excluded.storage_key,
    description = excluded.description,
    status = excluded.status,
    updated_at = excluded.updated_at;

INSERT INTO factor_definition (
    factor_id,
    version,
    factor_name,
    category,
    compute_ref,
    params,
    output_columns,
    storage_key,
    description,
    status,
    created_at,
    updated_at
) VALUES (
    'macd_12_26_9',
    'v1',
    'MACD(12,26,9)',
    'trend',
    'modules.factors.builtin.trend:MacdFactor',
    '{"fast":12,"signal":9,"slow":26}',
    '["macd_dif_12_26_9","macd_dea_12_26_9","macd_hist_12_26_9"]',
    'macd/v1/fast_12__slow_26__signal_9',
    '默认内置 MACD 因子定义',
    'active',
    '2025-01-01 00:00:00',
    '2025-01-01 00:00:00'
)
ON CONFLICT(factor_id, version) DO UPDATE SET
    factor_name = excluded.factor_name,
    category = excluded.category,
    compute_ref = excluded.compute_ref,
    params = excluded.params,
    output_columns = excluded.output_columns,
    storage_key = excluded.storage_key,
    description = excluded.description,
    status = excluded.status,
    updated_at = excluded.updated_at;

INSERT INTO factor_definition (
    factor_id,
    version,
    factor_name,
    category,
    compute_ref,
    params,
    output_columns,
    storage_key,
    description,
    status,
    created_at,
    updated_at
) VALUES (
    'boll_20_2',
    'v1',
    '布林带(20,2)',
    'volatility',
    'modules.factors.builtin.volatility:BollingerBandFactor',
    '{"num_std":2,"window":20}',
    '["boll_mid_20_2","boll_upper_20_2","boll_lower_20_2"]',
    'boll/v1/window_20__num_std_2',
    '默认内置布林带因子定义',
    'active',
    '2025-01-01 00:00:00',
    '2025-01-01 00:00:00'
)
ON CONFLICT(factor_id, version) DO UPDATE SET
    factor_name = excluded.factor_name,
    category = excluded.category,
    compute_ref = excluded.compute_ref,
    params = excluded.params,
    output_columns = excluded.output_columns,
    storage_key = excluded.storage_key,
    description = excluded.description,
    status = excluded.status,
    updated_at = excluded.updated_at;
