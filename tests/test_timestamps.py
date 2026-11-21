from engine.timestamps import schedule


def test_24_to_60_count_and_bounds():
    plans = schedule(240, 24.0, 60)
    assert len(plans) == 600
    assert all(0 <= p.src_a <= p.src_b < 240 for p in plans)
    assert plans[0].t == 0.0
    assert plans[0].src_a == 0


def test_24_to_60_weights_match_positions():
    plans = schedule(240, 24.0, 60)
    # 輸出第 3 幀時間 0.05s，來源位置 1.2 → src_a=1, t≈0.2
    assert plans[3].src_a == 1
    assert abs(plans[3].t - 0.2) < 1e-6


def test_30_to_60_is_alternating():
    plans = schedule(300, 30.0, 60)
    assert [round(p.t, 6) for p in plans[:4]] == [0.0, 0.5, 0.0, 0.5]


def test_60_to_60_passthrough():
    plans = schedule(60, 60.0, 60)
    assert all(p.src_a == p.src_b for p in plans)


def test_last_frame_never_exceeds():
    plans = schedule(10, 24.0, 60)
    assert max(p.src_b for p in plans) == 9


def test_empty_input():
    assert schedule(0, 24.0, 60) == []
