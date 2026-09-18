from __future__ import annotations

from collections.abc import Sequence


def rolling_mean(values: Sequence[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            result.append(None)
            continue
        current = values[idx + 1 - window : idx + 1]
        if any(value is None for value in current):
            result.append(None)
            continue
        numeric = [float(value) for value in current if value is not None]
        result.append(sum(numeric) / window)
    return result
