"""主視窗。"""
from __future__ import annotations

import pathlib
import sys
import time

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from engine.presets import all_presets
from engine.progress import parse
from engine.probe import probe

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".wmv"}
DEFAULT_OUTPUT_DIR = r"D:\AI視頻完成品"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("影片畫質增強")
        self.resize(760, 640)
        self.setAcceptDrops(True)
        self._input: str | None = None
        self._info = None
        self._proc: QProcess | None = None
        self._started_at = 0.0
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.drop_label = QLabel("把影片拖進來，或按「選擇影片」")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setMinimumHeight(90)
        self.drop_label.setStyleSheet(
            "border: 2px dashed #666; border-radius: 8px; color: #aaa; padding: 12px;")
        layout.addWidget(self.drop_label)

        pick = QPushButton("選擇影片")
        pick.clicked.connect(self._pick_file)
        layout.addWidget(pick)

        form = QFormLayout()
        self.preset_combo = QComboBox()
        for p in all_presets():
            self.preset_combo.addItem(p.label, p.name)
        form.addRow("預設", self.preset_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItem("跟隨預設（快，輕量模型）", "auto")
        self.model_combo.addItem("通用輕量 x4（最快）", "light")
        self.model_combo.addItem("強力 x2（慢約 3 倍）", "x2plus")
        self.model_combo.addItem("強力 x4（慢約 10 倍）", "x4plus")
        self.model_combo.addItem("動漫強力 x4（慢約 4 倍）", "anime-x4")
        self.model_combo.currentIndexChanged.connect(self._update_hint)
        form.addRow("超分模型", self.model_combo)

        self.model_hint = QLabel("")
        self.model_hint.setStyleSheet("color: #888;")
        self.model_hint.setWordWrap(True)
        form.addRow("", self.model_hint)

        self.edit_title = QLineEdit()
        self.edit_subtitle = QLineEdit()
        form.addRow("主題", self.edit_title)
        form.addRow("副題", self.edit_subtitle)

        out_row = QHBoxLayout()
        self.edit_outdir = QLineEdit(DEFAULT_OUTPUT_DIR)
        browse = QPushButton("…")
        browse.clicked.connect(self._pick_outdir)
        out_row.addWidget(self.edit_outdir)
        out_row.addWidget(browse)
        form.addRow("輸出目錄", out_row)
        layout.addLayout(form)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.status = QLabel("待機")
        layout.addWidget(self.status)

        btns = QHBoxLayout()
        self.btn_start = QPushButton("開始")
        self.btn_stop = QPushButton("中止")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        layout.addLayout(btns)

        log_box = QGroupBox("日誌")
        log_layout = QVBoxLayout(log_box)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        log_layout.addWidget(self.log)
        layout.addWidget(log_box, 1)

        self.setCentralWidget(root)

    # ---------- 檔案 ----------
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇影片", "", "影片 (*.mp4 *.mov *.mkv *.avi *.m4v *.wmv)")
        if path:
            self.set_input_path(path)

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "選擇輸出目錄", self.edit_outdir.text())
        if path:
            self.edit_outdir.setText(path)

    def set_input_path(self, path: str) -> None:
        self._input = path
        stem = pathlib.Path(path).stem
        title, _, subtitle = stem.partition("_")
        self.edit_title.setText(title)
        self.edit_subtitle.setText(subtitle)
        try:
            info = probe(path)
            self._info = info
            self.drop_label.setText(
                f"{pathlib.Path(path).name}\n{info.width}×{info.height}  "
                f"{info.fps:.2f}fps  {info.duration:.1f}s")
        except Exception as exc:  # noqa: BLE001
            self._info = None
            self.drop_label.setText(pathlib.Path(path).name)
            self._append(f"讀取資訊失敗：{exc}")
        self._update_hint()

    def _update_hint(self) -> None:
        choice = self.model_combo.currentData()
        info = self._info
        if info is None or choice == "auto":
            self.model_hint.setText("")
            return
        need = 2160 / max(1, info.height)
        if choice == "anime-x4":
            self.model_hint.setText("動漫／插畫專用，線條比輕量版銳利；實景素材不適用")
        elif choice == "light":
            self.model_hint.setText(
                f"此素材約需 {need:.2f}×，通用輕量模型走 4× 後縮回 4K，速度最快")
        elif choice == "x2plus":
            if need <= 2.2:
                self.model_hint.setText(f"此素材約需 {need:.2f}×，x2 足夠，畫質最佳")
            else:
                self.model_hint.setText(
                    f"此素材約需 {need:.2f}×，x2 只能到 {info.height * 2}p，"
                    "剩下靠插值，會偏糊；建議改用 x4")
        else:
            self.model_hint.setText(
                f"此素材約需 {need:.2f}×，x4 會過度放大後縮回 4K，較慢且不一定更好")

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if pathlib.Path(path).suffix.lower() in VIDEO_EXT:
                self.set_input_path(path)
                break

    # ---------- 執行 ----------
    def _output_path(self) -> str:
        title = self.edit_title.text().strip() or "output"
        subtitle = self.edit_subtitle.text().strip()
        name = f"{title}_{subtitle}" if subtitle else title
        return str(pathlib.Path(self.edit_outdir.text()) / f"{name}.mp4")

    def _start(self) -> None:
        if not self._input:
            QMessageBox.warning(self, "缺少輸入", "先選一段影片。")
            return
        out = self._output_path()
        args = [
            str(PROJECT_ROOT / "app" / "worker.py"),
            "--input", self._input,
            "--output", out,
            "--preset", self.preset_combo.currentData(),
            "--model", self.model_combo.currentData(),
            "--models-dir", str(PROJECT_ROOT / "models"),
        ]
        self._proc = QProcess(self)
        self._proc.setWorkingDirectory(str(PROJECT_ROOT))
        self._proc.setProcessChannelMode(QProcess.SeparateChannels)
        self._proc.readyReadStandardError.connect(self._read_stderr)
        self._proc.finished.connect(self._finished)
        self._started_at = time.time()
        self.progress.setValue(0)
        self.status.setText("啟動中…")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._append(f"輸出：{out}")
        self._proc.start(sys.executable, args)

    def _read_stderr(self) -> None:
        if not self._proc:
            return
        raw = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace")
        for line in raw.splitlines():
            msg = parse(line)
            if msg and msg.get("total"):
                pct = int(msg["done"] * 100 / msg["total"])
                self.progress.setValue(min(100, pct))
                self.status.setText(f"{msg['stage']}  {msg['done']}/{msg['total']}")
            elif line.strip():
                self._append(line)

    def _stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.NotRunning:
            self._append("使用者中止")
            self._proc.terminate()
            if not self._proc.waitForFinished(3000):
                self._proc.kill()

    def _finished(self, code: int, _status) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if code == 0:
            self.progress.setValue(100)
            elapsed = time.time() - self._started_at
            self.status.setText(f"完成，耗時 {elapsed:.1f} 秒")
            self._append(f"完成：{self._output_path()}")
        elif code == 3:
            self.status.setText("已拒絕：素材不符合條件")
        else:
            self.status.setText(f"失敗（退出碼 {code}）")

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)
