import polars as pl


class FactorProcessor:
    @staticmethod
    def winsorize(series: pl.Series, lower=0.01, upper=0.99) -> pl.Series:
        """去极值"""
        q_low = series.quantile(lower)
        q_high = series.quantile(upper)
        return series.clip(q_low, q_high)

    @staticmethod
    def standardize(series: pl.Series) -> pl.Series:
        """Z-score标准化"""
        return (series - series.mean()) / series.std()
