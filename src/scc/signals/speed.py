from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Iterable, Sequence


def calc_speed(snapshots: Sequence[tuple[datetime, int]], window: int) -> float:
    """Calculate view growth over the last ``window`` minutes."""
    if not snapshots:
        return 0.0
    snapshots = sorted(snapshots, key=lambda x: x[0])
    end_time, end_views = snapshots[-1]
    start_time = end_time - timedelta(minutes=window)
    start_views = end_views
    for ts, views in reversed(snapshots):
        if ts <= start_time:
            start_views = views
            break
    return max(end_views - start_views, 0)


def calc_zscore(value: float, history: Iterable[float]) -> float:
    data = list(history)
    if not data:
        return 0.0
    m = median(data)
    mad = median([abs(x - m) for x in data])
    if mad == 0:
        return 0.0
    return (value - m) / mad
