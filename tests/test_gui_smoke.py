import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_window_builds_with_controls(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    assert w.cb_sr.isChecked() and w.cb_fi.isChecked()
    assert w.content_combo.count() == 2
    assert w.quality_combo.count() == 3
    assert w.fps_combo.count() == 2
    assert w.profile_combo.count() == 3
    assert w.btn_start.isEnabled() and not w.btn_stop.isEnabled()


def test_anime_content_offers_two_qualities(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.content_combo.setCurrentIndex(w.content_combo.findData("anime"))
    assert w.quality_combo.count() == 2
    w.content_combo.setCurrentIndex(w.content_combo.findData("live"))
    assert w.quality_combo.count() == 3


def test_unchecking_sr_disables_quality_controls(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.cb_sr.setChecked(False)
    assert not w.content_combo.isEnabled()
    assert not w.quality_combo.isEnabled()
    w.cb_sr.setChecked(True)
    assert w.content_combo.isEnabled()
    assert w.quality_combo.isEnabled()


def test_unchecking_fi_disables_fps_combo(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.cb_fi.setChecked(False)
    assert not w.fps_combo.isEnabled()


def test_current_model_follows_quality_and_height(app, make_clip):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    assert w._current_model() == "x2plus"          # 實拍＋標準，預設 1080p
    w.content_combo.setCurrentIndex(w.content_combo.findData("anime"))
    assert w._current_model() == "anime-x4"        # 動畫＋最佳
    w.quality_combo.setCurrentIndex(w.quality_combo.findData("fast"))
    assert w._current_model() == "anime"           # 動畫＋快

    w.content_combo.setCurrentIndex(w.content_combo.findData("live"))
    w.set_input_path(make_clip(name="低清_480p.mp4", width=320, height=240))
    w.quality_combo.setCurrentIndex(w.quality_combo.findData("standard"))
    assert w._current_model() == "light"           # 低於 1000p，x2 到不了 4K


def test_name_derived_from_filename(app, make_clip):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.set_input_path(make_clip(name="相對論_時空扭曲結構.mp4"))
    assert w.edit_title.text() == "相對論"
    assert w.edit_subtitle.text() == "時空扭曲結構"


def test_name_without_underscore(app, make_clip):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.set_input_path(make_clip(name="摩擦力消失10秒.mp4"))
    assert w.edit_title.text() == "摩擦力消失10秒"
    assert w.edit_subtitle.text() == ""


def test_output_path_uses_dir_and_names(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.edit_outdir.setText(r"D:\tmp")
    w.edit_title.setText("主題")
    w.edit_subtitle.setText("副題")
    assert w._output_path().endswith(r"D:\tmp\主題_副題.mp4")


def test_output_uses_enhanced_suffix_when_names_are_unchanged(app, make_clip, tmp_path):
    from pathlib import Path
    from app.ui.main_window import MainWindow

    w = MainWindow()
    w.set_input_path(make_clip(name="input_clip.mp4"))
    w.edit_outdir.setText(str(tmp_path))
    assert Path(w._output_path()) == tmp_path / "input_clip_enhanced.mp4"
