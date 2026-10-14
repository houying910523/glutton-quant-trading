from __future__ import annotations

from dataclasses import dataclass
from statistics import linear_regression
from typing import Any, Mapping

import polars as pl

from modules.core import Context, Factor
from modules.core.context import StockDailyData, ParamsProperty

# 识别窗口为最近 40 个交易日；由于 MA5 需要预热，所以实际需要 44 天收盘价。
BOX_WINDOW = 40
SMOOTHING_WINDOW = 5
INPUT_WINDOW = BOX_WINDOW + SMOOTHING_WINDOW - 1
# 用 3 点窗口找局部波峰/波谷：中心点需高于/低于左右各 1 个点。
EXTREMA_RADIUS = 1
MIN_EXTREMA_COUNT = 2
# 允许边界在 40 日内轻微漂移，但首尾漂移比例不能超过 10%。
MAX_BOUNDARY_DRIFT_RATIO = 0.10
# 箱体高度需要落在 10% ~ 25% 之间。
MIN_BOX_HEIGHT_RATIO = 0.10
MAX_BOX_HEIGHT_RATIO = 0.30
# 最新收盘价在箱体内，或者最近 3 天至少 2 天仍在箱体内。
RECENT_WINDOW = 3
MIN_RECENT_INSIDE_COUNT = 2


@dataclass(frozen=True)
class BoundaryLine:
    slope: float
    intercept: float

    def value_at(self, index: float) -> float:
        return self.slope * index + self.intercept


@dataclass(frozen=True)
class EvaluationResult:
    matched: bool
    first_failure_reason: str | None
    condition_results: dict[str, bool]
    details: dict[str, float | int | bool | None]


class BoxConsolidationMatchFactor(Factor):
    """
    使用 MA5 平滑后的局部波峰/波谷回归线识别近期箱体震荡。

    当前实现遵循以下约束：
    1. 只看最近 40 个交易日对应的平滑窗口；
    2. 用 MA5 平滑序列识别局部波峰/波谷；
    3. 波峰和波谷各至少 2 个；
    4. 对波峰和波谷分别做线性回归，得到上沿和下沿；
    5. 上下沿在窗口内的首尾漂移比例都必须小于 8%；
    6. 箱体高度必须在 10% ~ 25% 之间；
    7. 最新收盘价仍在箱体内，或者最近 3 天至少 2 天仍在箱体内。
    """

    name = "box_consolidation_match"
    version = "v1"
    value_type = "bool"
    params_schema = [
        ParamsProperty(
            name="box_window_size",
            type="int",
            default=BOX_WINDOW,
            description="箱体窗口大小",
        ),
        ParamsProperty(
            name="smoothing_window_size",
            type="int",
            default=SMOOTHING_WINDOW,
            description="平滑窗口大小",
        ),
        ParamsProperty(
            name="extrema_radius",
            type="int",
            default=EXTREMA_RADIUS,
            description="波峰/波谷半径",
        ),
        ParamsProperty(
            name="min_extrema_count",
            type="int",
            default=MIN_EXTREMA_COUNT,
            description="波峰/波谷数量",
        ),
        ParamsProperty(
            name="max_boundary_drift_ratio",
            type="float",
            default=MAX_BOUNDARY_DRIFT_RATIO,
            description="边界漂移比例",
        ),
        ParamsProperty(
            name="min_box_height_ratio",
            type="float",
            default=MIN_BOX_HEIGHT_RATIO,
            description="箱体高度最小比例",
        ),
        ParamsProperty(
            name="max_box_height_ratio",
            type="float",
            default=MAX_BOX_HEIGHT_RATIO,
            description="箱体高度最大比例",
        ),
        ParamsProperty(
            name="recent_window",
            type="int",
            default=RECENT_WINDOW,
            description="最近窗口大小",
        ),
        ParamsProperty(
            name="min_recent_inside_count",
            type="int",
            default=MIN_RECENT_INSIDE_COUNT,
            description="最近窗口内仍在箱体内天数",
        ),
    ]

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        super().__init__(params)
        params = self.params
        self.box_window_size = params.get("box_window_size", BOX_WINDOW)
        self.smoothing_window_size = params.get(
            "smoothing_window_size", SMOOTHING_WINDOW
        )
        self.input_window_size = self.box_window_size + self.smoothing_window_size - 1
        self.extrema_radius = params.get("extrema_radius", EXTREMA_RADIUS)
        self.min_extrema_count = params.get("min_extrema_count", MIN_EXTREMA_COUNT)
        self.max_boundary_drift_ratio = params.get(
            "max_boundary_drift_ratio", MAX_BOUNDARY_DRIFT_RATIO
        )
        self.min_box_height_ratio = params.get(
            "min_box_height_ratio", MIN_BOX_HEIGHT_RATIO
        )
        self.max_box_height_ratio = params.get(
            "max_box_height_ratio", MAX_BOX_HEIGHT_RATIO
        )
        self.recent_window = params.get("recent_window", RECENT_WINDOW)
        self.min_recent_inside_count = params.get(
            "min_recent_inside_count", MIN_RECENT_INSIDE_COUNT
        )

    def inputs(self) -> list[str]:
        return ["close"]

    def compute(self, context: Context) -> dict[str, pl.DataFrame]:
        result: dict[str, pl.DataFrame] = {}
        for stock_daily_data in context.stock_daily_data:
            factor_frame = self._compute_stock_factor_frame(stock_daily_data)
            if factor_frame.height == 0:
                continue
            result[stock_daily_data.instrument_id] = factor_frame
        return result

    def _compute_stock_factor_frame(
        self, stock_daily_data: StockDailyData
    ) -> pl.DataFrame:
        frame = stock_daily_data.data.sort("trade_date")
        if frame.height == 0:
            return pl.DataFrame(
                schema={
                    "instrument_id": pl.Utf8,
                    "trade_date": pl.Date,
                    "factor_value": pl.Boolean,
                }
            )

        closes = [float(value) for value in frame["close"].to_list()]
        factor_values = [
            self.evaluate_closes(closes[: index + 1]).matched
            for index in range(len(closes))
        ]
        return pl.DataFrame(
            {
                "instrument_id": pl.Series(
                    "instrument_id",
                    [stock_daily_data.instrument_id] * frame.height,
                    dtype=pl.Utf8,
                ),
                "trade_date": frame["trade_date"],
                "factor_value": pl.Series(
                    factor_values,
                    dtype=pl.Boolean,
                ),
            }
        )

    def matches(self, stock_daily_data: StockDailyData) -> bool:
        frame = stock_daily_data.data.sort("trade_date").tail(self.input_window_size)
        closes = [float(value) for value in frame["close"].to_list()]
        return self.evaluate_closes(closes).matched

    def evaluate_closes(self, closes: list[float]) -> EvaluationResult:
        condition_results: dict[str, bool] = {
            "history": len(closes) >= self.input_window_size,
        }
        details: dict[str, float | int | bool | None] = {
            "close_count": len(closes),
            "peak_count": 0,
            "valley_count": 0,
            "upper_drift_ratio": None,
            "lower_drift_ratio": None,
            "box_height_ratio": None,
            "recent_inside_count": 0,
            "latest_inside": False,
        }
        if not condition_results["history"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="insufficient_history",
            )

        windowed_closes = closes[-self.input_window_size :]
        smoothed = self._moving_average(windowed_closes, self.smoothing_window_size)
        condition_results["smoothed_window"] = len(smoothed) == self.box_window_size
        if not condition_results["smoothed_window"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="invalid_smoothed_window",
            )

        peaks, valleys = self._collect_local_extrema(smoothed)
        details["peak_count"] = len(peaks)
        details["valley_count"] = len(valleys)
        condition_results["peak_count"] = len(peaks) >= self.min_extrema_count
        condition_results["valley_count"] = len(valleys) >= self.min_extrema_count
        if not condition_results["peak_count"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="insufficient_peaks",
            )
        if not condition_results["valley_count"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="insufficient_valleys",
            )

        upper_boundary = self._fit_boundary(peaks)
        lower_boundary = self._fit_boundary(valleys)
        condition_results["upper_boundary"] = upper_boundary is not None
        condition_results["lower_boundary"] = lower_boundary is not None
        if not condition_results["upper_boundary"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="upper_boundary_fit_failed",
            )
        if not condition_results["lower_boundary"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="lower_boundary_fit_failed",
            )

        upper_drift_ratio = self._boundary_drift_ratio(upper_boundary)
        lower_drift_ratio = self._boundary_drift_ratio(lower_boundary)
        details["upper_drift_ratio"] = upper_drift_ratio
        details["lower_drift_ratio"] = lower_drift_ratio
        condition_results["upper_boundary_drift"] = (
            upper_drift_ratio is not None
            and upper_drift_ratio < self.max_boundary_drift_ratio
        )
        condition_results["lower_boundary_drift"] = (
            lower_drift_ratio is not None
            and lower_drift_ratio < self.max_boundary_drift_ratio
        )
        if not condition_results["upper_boundary_drift"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="upper_boundary_drift_too_large",
            )
        if not condition_results["lower_boundary_drift"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="lower_boundary_drift_too_large",
            )

        box_height_ratio = self._box_height_ratio(upper_boundary, lower_boundary)
        details["box_height_ratio"] = box_height_ratio
        condition_results["box_height"] = (
            box_height_ratio is not None
            and self.min_box_height_ratio
            <= box_height_ratio
            <= self.max_box_height_ratio
        )
        if not condition_results["box_height"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="box_height_out_of_range",
            )

        recent_inside_count, latest_inside = self._recent_inside_summary(
            windowed_closes,
            upper_boundary,
            lower_boundary,
        )
        details["recent_inside_count"] = recent_inside_count
        details["latest_inside"] = latest_inside
        condition_results["recent_inside"] = (
            latest_inside or recent_inside_count >= self.min_recent_inside_count
        )
        if not condition_results["recent_inside"]:
            return self._evaluation_result(
                condition_results,
                details,
                first_failure_reason="recent_prices_outside_box",
            )

        return self._evaluation_result(
            condition_results,
            details,
            first_failure_reason=None,
        )

    @staticmethod
    def _evaluation_result(
        condition_results: dict[str, bool],
        details: dict[str, float | int | bool | None],
        *,
        first_failure_reason: str | None,
    ) -> EvaluationResult:
        return EvaluationResult(
            matched=first_failure_reason is None,
            first_failure_reason=first_failure_reason,
            condition_results=dict(condition_results),
            details=dict(details),
        )

    @staticmethod
    def _moving_average(values: list[float], window: int) -> list[float]:
        if len(values) < window:
            return []
        return [
            sum(values[index : index + window]) / window
            for index in range(len(values) - window + 1)
        ]

    def _collect_local_extrema(
        self, values: list[float]
    ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        peaks: list[tuple[int, float]] = []
        valleys: list[tuple[int, float]] = []
        for index in range(self.extrema_radius, len(values) - self.extrema_radius):
            neighbors = (
                values[index - self.extrema_radius : index]
                + values[index + 1 : index + self.extrema_radius + 1]
            )
            current = values[index]
            if all(current > value for value in neighbors):
                peaks.append((index, current))
            if all(current < value for value in neighbors):
                valleys.append((index, current))
        return peaks, valleys

    def _fit_boundary(self, points: list[tuple[int, float]]) -> BoundaryLine | None:
        if len(points) < self.min_extrema_count:
            return None
        x_values = [float(index) for index, _ in points]
        y_values = [price for _, price in points]
        slope, intercept = linear_regression(x_values, y_values)
        return BoundaryLine(slope=slope, intercept=intercept)

    def _has_valid_boundary_drift(self, boundary: BoundaryLine) -> bool:
        drift_ratio = self._boundary_drift_ratio(boundary)
        return drift_ratio is not None and drift_ratio < self.max_boundary_drift_ratio

    def _boundary_drift_ratio(self, boundary: BoundaryLine) -> float | None:
        start_value = boundary.value_at(0.0)
        end_value = boundary.value_at(self.box_window_size - 1)
        center_value = (start_value + end_value) / 2
        if center_value <= 0:
            return None
        return abs(end_value - start_value) / center_value

    def _has_valid_box_height(
        self,
        upper_boundary: BoundaryLine,
        lower_boundary: BoundaryLine,
    ) -> bool:
        height_ratio = self._box_height_ratio(upper_boundary, lower_boundary)
        return (
            height_ratio is not None
            and self.min_box_height_ratio <= height_ratio <= self.max_box_height_ratio
        )

    def _box_height_ratio(
        self,
        upper_boundary: BoundaryLine,
        lower_boundary: BoundaryLine,
    ) -> float | None:
        midpoint = (self.box_window_size - 1) / 2
        upper_value = upper_boundary.value_at(midpoint)
        lower_value = lower_boundary.value_at(midpoint)
        if lower_value <= 0 or upper_value <= lower_value:
            return None
        return (upper_value - lower_value) / lower_value

    def _is_recently_inside_box(
        self,
        closes: list[float],
        upper_boundary: BoundaryLine,
        lower_boundary: BoundaryLine,
    ) -> bool:
        recent_inside_count, latest_inside = self._recent_inside_summary(
            closes,
            upper_boundary,
            lower_boundary,
        )
        return latest_inside or recent_inside_count >= self.min_recent_inside_count

    def _recent_inside_summary(
        self,
        closes: list[float],
        upper_boundary: BoundaryLine,
        lower_boundary: BoundaryLine,
    ) -> tuple[int, bool]:
        if len(closes) < self.input_window_size:
            return 0, False

        recent_inside_count = 0
        for offset in range(self.recent_window):
            raw_index = len(closes) - self.recent_window + offset
            boundary_index = raw_index - (self.box_window_size - 1)
            lower_value = lower_boundary.value_at(boundary_index)
            upper_value = upper_boundary.value_at(boundary_index)
            if lower_value <= closes[raw_index] <= upper_value:
                recent_inside_count += 1

        latest_boundary_index = len(closes) - 1 - (self.smoothing_window_size - 1)
        latest_lower = lower_boundary.value_at(latest_boundary_index)
        latest_upper = upper_boundary.value_at(latest_boundary_index)
        latest_inside = latest_lower <= closes[-1] <= latest_upper
        return recent_inside_count, latest_inside
