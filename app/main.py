import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from app.ui import config, i18n
from app.ui.main_window import MainWindow
from app.ui.theme import QSS, app_font
from app.ui.wizard import SetupWizard

LOG_FILE = Path(tempfile.gettempdir()) / "video-enhance-error.log"


def _report(exc: BaseException) -> None:
    text = "".join(traceback.format_exception(exc))
    LOG_FILE.write_text(text, encoding="utf-8")
    if QApplication.instance() is None:
        return
    box = QMessageBox()
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(i18n.tr("app.title"))
    box.setText("啟動失敗，程式已中止。")
    box.setDetailedText(f"{text}\n\n已寫入：{LOG_FILE}")
    box.exec()


def _ask_output_dir() -> None:
    """首啟問一次成品放哪裡，之後記住。"""
    if config.SETTINGS.contains("output_dir"):
        return
    path = QFileDialog.getExistingDirectory(
        None, i18n.tr("dlg.pick_outdir"), str(config.videos_dir()))
    config.save_output_dir(path or config.default_output_dir())


def main() -> int:
    # 打包後只有一個 exe：用 --worker 讓同一支程式切到子進程模式。
    if "--worker" in sys.argv:
        from app.worker import main as worker_main

        return worker_main(sys.argv[sys.argv.index("--worker") + 1:])

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    i18n.set_language(config.language() or i18n.detect_language())
    app.setFont(app_font())
    app.setStyleSheet(QSS)
    _ask_output_dir()
    if not config.setup_done():
        if SetupWizard().exec() != QDialog.Accepted:
            return 0
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, SystemExit):
            raise
        _report(exc)
        sys.exit(1)
