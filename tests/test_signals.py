from datetime import datetime, timedelta

from scc.signals.speed import calc_speed, calc_zscore


def test_calc_speed_and_zscore():
    now = datetime.utcnow()
    snaps = [(now - timedelta(minutes=60), 0), (now, 20)]
    v60 = calc_speed(snaps, 60)
    assert v60 == 20
    z = calc_zscore(20, [10, 12, 14, 16, 18])
    assert round(z, 2) == 3.0
