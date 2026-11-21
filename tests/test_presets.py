from engine.presets import load, all_presets


def test_balanced_values():
    p = load("balanced")
    assert (p.do_sr, p.do_fi, p.tile, p.encoder, p.crf) == (True, True, 768, "hevc_nvenc", 19)


def test_quality_uses_x265():
    p = load("quality")
    assert (p.encoder, p.crf) == ("libx265", 18)


def test_fast_uses_higher_cq():
    p = load("fast")
    assert (p.tile, p.encoder, p.crf) == (768, "hevc_nvenc", 21)


def test_fi_only_disables_sr():
    assert load("fi_only").do_sr is False


def test_sr_only_disables_fi():
    assert load("sr_only").do_fi is False


def test_all_five_present():
    assert {p.name for p in all_presets()} == {"balanced", "quality", "fast", "fi_only", "sr_only"}
