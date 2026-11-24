"""主視窗。"""
from __future__ import annotations

import pathlib
import sys
import time

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
    QWidget,
)

from engine.encoders import all_profiles
from engine.policy import qualities_for, resolve_model
from engine.progress import parse
from engine.probe import probe

from . import config
from .glass import GlassWindow
from .i18n import tr

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".wmv"}


class MainWindow(GlassWindow):
    def __init__(self):
        super().__init__(tr("app.title"))
        self.resize(1000, 726)
        self.setAcceptDrops(True)
        self._input: str | None = None
        self._info = None
        self._proc: QProcess | None = None
        self._started_at = 0.0
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        left = QWidget()
        left.setFixedWidth(408)
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(12)
        left_box.addWidget(self._drop_card())
        left_box.addWidget(self._settings_card(), 1)

        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(12)
        right_box.addWidget(self._progress_card())
        right_box.addWidget(self._log_card(), 1)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(left)
        body.addWidget(right, 1)

        self.content_layout.addLayout(body, 1)
        self.content_layout.addWidget(self._action_bar())

        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)
        self._sync_enabled()

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 16)
        box.setSpacing(12)
        return card, box

    @staticmethod
    def _field(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("field")
        return label

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    @staticmethod
    def _hline() -> QFrame:
        line = QFrame()
        line.setObjectName("hline")
        line.setFixedHeight(1)
        return line

    def _drop_card(self) -> QWidget:
        card, box = self._card()
        self._zone = QFrame()
        self._zone.setObjectName("dropZone")
        self._zone.setMinimumHeight(88)
        zone_box = QVBoxLayout(self._zone)
        zone_box.setContentsMargins(14, 14, 14, 14)

        self.drop_label = QLabel(tr("drop.hint"))
        self.drop_label.setObjectName("dropLabel")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setWordWrap(True)
        zone_box.addWidget(self.drop_label)
        box.addWidget(self._zone)

        pick = QPushButton(tr("btn.pick"))
        pick.setObjectName("ghost")
        pick.setCursor(Qt.PointingHandCursor)
        pick.clicked.connect(self._pick_file)
        box.addWidget(pick)
        return card

    def _settings_card(self) -> QWidget:
        card, box = self._card()
        box.addWidget(self._section(tr("card.settings")))

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.cb_sr = QCheckBox(tr("chk.sr"))
        self.cb_sr.setChecked(True)
        self.cb_sr.toggled.connect(self._sync_enabled)
        form.addRow(self.cb_sr)

        self.content_combo = QComboBox()
        self.content_combo.addItem(tr("content.live"), "live")
        self.content_combo.addItem(tr("content.anime"), "anime")
        self.content_combo.currentIndexChanged.connect(self._sync_quality_options)
        form.addRow(self._field(tr("lbl.content")), self.content_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.currentIndexChanged.connect(self._update_hint)
        form.addRow(self._field(tr("lbl.quality")), self.quality_combo)
        self._sync_quality_options()

        self.model_hint = QLabel("")
        self.model_hint.setObjectName("hint")
        self.model_hint.setWordWrap(True)
        form.addRow("", self.model_hint)

        form.addRow(self._hline())

        self.cb_fi = QCheckBox(tr("chk.fi"))
        self.cb_fi.setChecked(True)
        self.cb_fi.toggled.connect(self._sync_enabled)
        form.addRow(self.cb_fi)

        self.fps_combo = QComboBox()
        self.fps_combo.addItem(tr("fps.60"), 60)
        self.fps_combo.addItem(tr("fps.120"), 120)
        self.fps_combo.currentIndexChanged.connect(self._update_hint)
        form.addRow(self._field(tr("lbl.fps")), self.fps_combo)

        form.addRow(self._hline())

        self.profile_combo = QComboBox()
        for p in all_profiles():
            self.profile_combo.addItem(tr(f"profile.{p.name}"), p.name)
        form.addRow(self._field(tr("lbl.profile")), self.profile_combo)

        form.addRow(self._hline())

        self.edit_title = QLineEdit()
        self.edit_subtitle = QLineEdit()
        form.addRow(self._field(tr("lbl.title")), self.edit_title)
        form.addRow(self._field(tr("lbl.subtitle")), self.edit_subtitle)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.edit_outdir = QLineEdit(config.output_dir())
        self.edit_outdir.editingFinished.connect(self._remember_output_dir)
        browse = QPushButton(tr("btn.browse"))
        browse.setObjectName("ghost")
        browse.setFixedWidth(44)
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._pick_outdir)
        out_row.addWidget(self.edit_outdir, 1)
        out_row.addWidget(browse)
        form.addRow(self._field(tr("lbl.outdir")), out_row)

        box.addLayout(form)
        box.addStretch(1)
        return card

    def _progress_card(self) -> QWidget:
        card, box = self._card()
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self._section(tr("card.progress")))
        head.addStretch(1)
        self.pct_label = QLabel("0%")
        self.pct_label.setObjectName("pct")
        head.addWidget(self.pct_label)
        box.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        box.addWidget(self.progress)
        return card

    def _log_card(self) -> QWidget:
        card, box = self._card()
        box.setSpacing(10)
        box.addWidget(self._section(tr("card.log")))

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFrameShape(QFrame.NoFrame)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        box.addWidget(self.log, 1)
        return card

    def _action_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(10)

        self.status = QLabel(tr("status.idle"))
        self.status.setObjectName("status")
        row.addWidget(self.status)
        row.addStretch(1)

        self.btn_stop = QPushButton(tr("btn.stop"))
        self.btn_stop.setObjectName("ghost")
        self.btn_stop.setFixedWidth(96)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop)

        self.btn_start = QPushButton(tr("btn.start"))
        self.btn_start.setObjectName("primary")
        self.btn_start.setFixedWidth(136)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._start)

        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_start)
        return bar

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ---------- 檔案 ----------
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.pick_video"), "", tr("dlg.video_filter"))
        if path:
            self.set_input_path(path)

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("dlg.pick_outdir"), self.edit_outdir.text())
        if path:
            self.edit_outdir.setText(path)
            self._remember_output_dir()

    def _remember_output_dir(self) -> None:
        config.save_output_dir(self.edit_outdir.text().strip())

    def set_input_path(self, path: str) -> None:
        self._input = path
        stem = pathlib.Path(path).stem
        title, _, subtitle = stem.partition("_")
        self.edit_title.setText(title)
        self.edit_subtitle.setText(subtitle)
        try:
            info = probe(path)
            self._info = info
            self.drop_label.setText(tr(
                "drop.loaded", name=pathlib.Path(path).name, width=info.width,
                height=info.height, fps=info.fps, duration=info.duration))
        except Exception as exc:  # noqa: BLE001
            self._info = None
            self.drop_label.setText(pathlib.Path(path).name)
            self._append(tr("log.read_fail", error=exc))
        self._update_hint()

    def _sync_enabled(self) -> None:
        upscaling = self.cb_sr.isChecked()
        self.content_combo.setEnabled(upscaling)
        self.quality_combo.setEnabled(upscaling)
        self.fps_combo.setEnabled(self.cb_fi.isChecked())
        self._update_hint()

    def _sync_quality_options(self) -> None:
        content = self.content_combo.currentData()
        options = qualities_for(content)
        fallback = "best" if content == "anime" else "standard"
        previous = self.quality_combo.currentData()
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        for quality in options:
            self.quality_combo.addItem(tr(f"quality.{quality}"), quality)
        target = previous if previous in options else fallback
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(target)))
        self.quality_combo.blockSignals(False)
        self._update_hint()

    def _current_model(self) -> str:
        height = self._info.height if self._info is not None else 1080
        return resolve_model(self.quality_combo.currentData(),
                             self.content_combo.currentData(), height)

    def _update_hint(self) -> None:
        if not hasattr(self, "model_hint"):
            return
        parts: list[str] = []
        if self.cb_sr.isChecked():
            quality = self.quality_combo.currentData()
            content = self.content_combo.currentData()
            if quality:
                parts.append(tr(f"hint.{quality}_{content}"))
        else:
            parts.append(tr("hint.no_sr"))

        if self.cb_fi.isChecked():
            target = self.fps_combo.currentData()
            if self._info is not None and target and target <= round(self._info.fps):
                parts.append(tr("hint.fi_skip", fps=self._info.fps, target=target))
        else:
            parts.append(tr("hint.no_fi"))

        self.model_hint.setText(tr("hint.sep").join(parts))
        self.model_hint.setVisible(bool(self.model_hint.text()))

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            self._zone.setProperty("drag", True)
            self._repolish(self._zone)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self._zone.setProperty("drag", False)
        self._repolish(self._zone)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        self._zone.setProperty("drag", False)
        self._repolish(self._zone)
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
            QMessageBox.warning(self, tr("msg.no_input.title"), tr("msg.no_input.body"))
            return
        out = self._output_path()
        self._remember_output_dir()
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--worker"]
        else:
            cmd = [sys.executable, str(PROJECT_ROOT / "app" / "worker.py")]
        args = cmd + [
            "--input", self._input,
            "--output", out,
            "--profile", self.profile_combo.currentData(),
            "--model", self._current_model(),
            "--fps", str(self.fps_combo.currentData()),
            "--sr" if self.cb_sr.isChecked() else "--no-sr",
            "--fi" if self.cb_fi.isChecked() else "--no-fi",
            "--models-dir", config.models_dir(),
        ]
        self._proc = QProcess(self)
        self._proc.setWorkingDirectory(str(PROJECT_ROOT))
        self._proc.setProcessChannelMode(QProcess.SeparateChannels)
        self._proc.readyReadStandardError.connect(self._read_stderr)
        self._proc.finished.connect(self._finished)
        self._started_at = time.time()
        self.progress.setValue(0)
        self.pct_label.setText("0%")
        self.status.setText(tr("status.starting"))
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._append(tr("log.output", path=out))
        self._proc.start(args[0], args[1:])

    def _read_stderr(self) -> None:
        if not self._proc:
            return
        raw = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace")
        for line in raw.splitlines():
            msg = parse(line)
            if msg and msg.get("total"):
                pct = int(msg["done"] * 100 / msg["total"])
                self.progress.setValue(min(100, pct))
                self.pct_label.setText(f"{min(100, pct)}%")
                self.status.setText(f"{msg['stage']}  {msg['done']}/{msg['total']}")
            elif line.strip():
                self._append(line)

    def _stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.NotRunning:
            self._append(tr("log.aborted"))
            self._proc.terminate()
            if not self._proc.waitForFinished(3000):
                self._proc.kill()

    def _finished(self, code: int, _status) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if code == 0:
            self.progress.setValue(100)
            self.pct_label.setText("100%")
            elapsed = time.time() - self._started_at
            self.status.setText(tr("status.done", seconds=elapsed))
            self._append(tr("log.output", path=self._output_path()))
        elif code == 3:
            self.status.setText(tr("status.rejected"))
        else:
            self.status.setText(tr("status.failed", code=code))

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)
