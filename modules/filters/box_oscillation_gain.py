from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.core import Filter
from modules.core.context import StockDailyData


# 最近 60 个交易日近似表示“最近 3 个月”的观察窗口。
WINDOW_SIZE = 60
# 同一边界的局部高点/低点分位数离散度不能过大，避免把松散波动当成箱体边界。
BOUNDARY_SPREAD_LIMIT = 0.08
# 边界首尾漂移幅度不能超过 5%，用于排除斜向通道，只保留近似水平边界。
BOUNDARY_DRIFT_LIMIT = 0.05
# 用分位数构造稳定边界时，至少保留 1% 的价格带宽，避免零宽度区间。
MIN_ZONE_BAND_RATIO = 0.01
# 箱体至少要出现 2 个局部高点和 2 个局部低点，避免把单边走势误判成震荡。
MIN_EXTREMA_COUNT = 2
# 至少要出现 4 次“上沿/下沿”触达，才能视为在两个价格区间之间往返震荡。
MIN_ZONE_TOUCHES = 4
# 箱体高度过小更像噪声，过大更像宽幅波动或通道。
MIN_BOX_HEIGHT_RATIO = 0.04
MAX_BOX_HEIGHT_RATIO = 0.30
# 最近 5 个交易日里至少 4 天收盘仍在箱体内，且最新收盘价也必须位于箱体内。
RECENT_WINDOW = 5
MIN_RECENT_INSIDE_COUNT = 4


@dataclass(frozen=True)
class BoundaryZone:
    lower: float
    upper: float
    center: float
    points: list[tuple[int, float]]


class BoxOscillationGainFilter(Filter):
    """
    兼容历史命名的水平箱体筛选器。

    当前版本不再做“当日上涨/突破”识别，而是专注识别最近 60 个交易日内：

    1. 存在稳定的上沿与下沿；
    2. 上下沿近似水平，而不是上升/下降通道；
    3. 价格在上下沿之间至少往返触达 4 次；
    4. 箱体高度处于合理范围；
    5. 最近 5 个交易日里，价格仍然停留在箱体内部。

    为了降低异常影线的干扰：
    - 同一天如果同时满足局部高点和局部低点，会直接跳过；
    - 用局部高点/低点的分位数构造稳定边界，而不是直接用 min/max。
    """

    name = "box_oscillation_gain"
    params: dict[str, Any] = {}

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        return [item for item in data if self._matches(item)]

    @classmethod
    def _matches(cls, stock_daily_data: StockDailyData) -> bool:
        frame = stock_daily_data.data.sort("trade_date").tail(WINDOW_SIZE)
        if frame.height < WINDOW_SIZE:
            return False

        closes = [float(value) for value in frame["close"].to_list()]
        highs = [float(value) for value in frame["high"].to_list()]
        lows = [float(value) for value in frame["low"].to_list()]
        extrema_points = cls._collect_extrema_points(highs, lows)
        upper_points = [
            (index, price) for index, kind, price in extrema_points if kind == "upper"
        ]
        lower_points = [
            (index, price) for index, kind, price in extrema_points if kind == "lower"
        ]
        if (
            len(upper_points) < MIN_EXTREMA_COUNT
            or len(lower_points) < MIN_EXTREMA_COUNT
        ):
            return False

        upper_zone = cls._build_boundary_zone(upper_points)
        lower_zone = cls._build_boundary_zone(lower_points)
        if upper_zone is None or lower_zone is None:
            return False
        if not cls._is_horizontal_boundary(
            upper_zone
        ) or not cls._is_horizontal_boundary(lower_zone):
            return False
        if not cls._is_valid_box_height(upper_zone, lower_zone):
            return False
        if not cls._has_oscillation_between_zones(
            extrema_points, upper_zone, lower_zone
        ):
            return False
        return cls._is_recently_inside_box(closes, lower_zone.center, upper_zone.center)

    @staticmethod
    def _collect_extrema_points(
        highs: list[float],
        lows: list[float],
    ) -> list[tuple[int, str, float]]:
        # 首尾两天没有完整的左右邻居，无法判断局部拐点，所以只检查中间位置。
        extrema_points: list[tuple[int, str, float]] = []
        for index in range(1, len(highs) - 1):
            previous_high = highs[index - 1]
            current_high = highs[index]
            next_high = highs[index + 1]
            is_upper = current_high >= previous_high and current_high >= next_high
            is_upper = is_upper and (
                current_high > previous_high or current_high > next_high
            )

            previous_low = lows[index - 1]
            current_low = lows[index]
            next_low = lows[index + 1]
            is_lower = current_low <= previous_low and current_low <= next_low
            is_lower = is_lower and (
                current_low < previous_low or current_low < next_low
            )

            # 长上影/长下影的极端 K 线容易同时满足局部高点和局部低点，
            # 这类噪声会虚增“上下沿切换次数”，因此直接跳过。
            if is_upper and is_lower:
                continue
            if is_upper:
                extrema_points.append((index, "upper", current_high))
            if is_lower:
                extrema_points.append((index, "lower", current_low))

        extrema_points.sort(key=lambda item: item[0])
        return extrema_points

    @classmethod
    def _build_boundary_zone(
        cls,
        points: list[tuple[int, float]],
    ) -> BoundaryZone | None:
        if len(points) < MIN_EXTREMA_COUNT:
            return None

        prices = [price for _, price in points]
        center = cls._quantile(prices, 0.5)
        q1 = cls._quantile(prices, 0.25)
        q3 = cls._quantile(prices, 0.75)
        if center <= 0:
            return None

        band = max(q3 - q1, center * MIN_ZONE_BAND_RATIO)
        clustered_points = [
            (index, price) for index, price in points if abs(price - center) <= band
        ]
        if len(clustered_points) < MIN_EXTREMA_COUNT:
            return None

        clustered_prices = [price for _, price in clustered_points]
        clustered_center = cls._quantile(clustered_prices, 0.5)
        clustered_q1 = cls._quantile(clustered_prices, 0.25)
        clustered_q3 = cls._quantile(clustered_prices, 0.75)
        if clustered_center <= 0:
            return None

        spread = clustered_q3 - clustered_q1
        if spread / clustered_center > BOUNDARY_SPREAD_LIMIT:
            return None

        zone_band = max(spread, clustered_center * MIN_ZONE_BAND_RATIO)
        return BoundaryZone(
            lower=clustered_center - zone_band,
            upper=clustered_center + zone_band,
            center=clustered_center,
            points=clustered_points,
        )

    @staticmethod
    def _quantile(values: list[float], quantile: float) -> float:
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]

        position = (len(sorted_values) - 1) * quantile
        lower_index = int(position)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        weight = position - lower_index
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        return lower_value + (upper_value - lower_value) * weight

    @staticmethod
    def _is_horizontal_boundary(zone: BoundaryZone) -> bool:
        if len(zone.points) < MIN_EXTREMA_COUNT or zone.center <= 0:
            return False

        indices = [index for index, _ in zone.points]
        prices = [price for _, price in zone.points]
        mean_index = sum(indices) / len(indices)
        mean_price = sum(prices) / len(prices)
        variance = sum((index - mean_index) ** 2 for index in indices)
        if variance == 0:
            return False

        covariance = sum(
            (index - mean_index) * (price - mean_price)
            for index, price in zip(indices, prices)
        )
        slope = covariance / variance
        drift = abs(slope * (max(indices) - min(indices)))
        return drift / zone.center <= BOUNDARY_DRIFT_LIMIT

    @staticmethod
    def _is_valid_box_height(
        upper_zone: BoundaryZone, lower_zone: BoundaryZone
    ) -> bool:
        if lower_zone.center <= 0 or upper_zone.center <= lower_zone.center:
            return False

        height_ratio = (upper_zone.center - lower_zone.center) / lower_zone.center
        return MIN_BOX_HEIGHT_RATIO <= height_ratio <= MAX_BOX_HEIGHT_RATIO

    @staticmethod
    def _has_oscillation_between_zones(
        extrema_points: list[tuple[int, str, float]],
        upper_zone: BoundaryZone,
        lower_zone: BoundaryZone,
    ) -> bool:
        zone_touches: list[str] = []
        for _, kind, price in extrema_points:
            if kind == "upper" and upper_zone.lower <= price <= upper_zone.upper:
                if not zone_touches or zone_touches[-1] != "upper":
                    zone_touches.append("upper")
                continue
            if kind == "lower" and lower_zone.lower <= price <= lower_zone.upper:
                if not zone_touches or zone_touches[-1] != "lower":
                    zone_touches.append("lower")

        if len(zone_touches) < MIN_ZONE_TOUCHES:
            return False
        return "upper" in zone_touches and "lower" in zone_touches

    @staticmethod
    def _is_recently_inside_box(
        closes: list[float],
        lower_boundary: float,
        upper_boundary: float,
    ) -> bool:
        if len(closes) < RECENT_WINDOW or upper_boundary <= lower_boundary:
            return False

        recent_closes = closes[-RECENT_WINDOW:]
        inside_count = sum(
            lower_boundary <= price <= upper_boundary for price in recent_closes
        )
        return (
            inside_count >= MIN_RECENT_INSIDE_COUNT
            and lower_boundary <= recent_closes[-1] <= upper_boundary
        )
