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


def test_near_integer_fps_snaps_to_source_frames():
    """幀率由 frame_count/duration 推算時帶微小誤差，原幀不該被當成插值幀。

    實測 1440p 素材：121 幀 / 2.0167 秒 = 59.99999fps，輸出到 120fps 時
    原本每個原幀都得到 t=0.99999983，導致 120 個原幀白跑一次補幀網路。
    """
    plans = schedule(121, 121 / 2.0166666666666666, 120)
    assert len(plans) == 242
    assert sum(1 for p in plans if p.t > 0) == 120
    assert all(p.t == 0.0 or abs(p.t - 0.5) < 1e-6 for p in plans)
