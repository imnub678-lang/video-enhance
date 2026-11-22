import pytest

from engine.encoders import all_profiles, load


def test_standard_uses_nvenc():
    p = load("standard")
    assert (p.encoder, p.crf) == ("hevc_nvenc", 19)


def test_fast_uses_higher_cq():
    p = load("fast")
    assert (p.encoder, p.crf) == ("hevc_nvenc", 21)


def test_small_uses_x265():
    p = load("small")
    assert (p.encoder, p.crf) == ("libx265", 18)


def test_all_three_present():
    assert {p.name for p in all_profiles()} == {"standard", "fast", "small"}


def test_missing_profile_raises():
    with pytest.raises(FileNotFoundError):
        load("nope")
