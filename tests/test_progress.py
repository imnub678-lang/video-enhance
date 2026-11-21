from engine.progress import parse


def test_parse_valid():
    assert parse('{"stage":"sr","done":1,"total":2}') == {"stage": "sr", "done": 1, "total": 2}


def test_parse_garbage():
    assert parse("ffmpeg: some error") is None


def test_parse_missing_stage():
    assert parse('{"done":1}') is None


def test_parse_broken_json():
    assert parse('{"stage":') is None
