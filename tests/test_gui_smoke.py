import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_window_builds_with_six_presets(app):
    from app.ui.main_window import MainWindow

    w = MainWindow()
    assert w.preset_combo.count() == 6
    assert w.btn_start.isEnabled() and not w.btn_stop.isEnabled()


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
