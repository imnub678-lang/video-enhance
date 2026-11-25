"""首啟精靈：掃描裝置 → 選模型 → 下載。"""
from __future__ import annotations

import pathlib

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from engine import backend
from engine.models import MODELS
from engine.policy import MODEL_CHOICES, tile_for_vram
from . import config
from .glass import apply_dwm_chrome
from .i18n import tr

ORDER = ("light", "anime", "anime-x4", "x2plus", "x4plus", "rife426")
SIZES_MB = {"light": 5, "anime": 3, "anime-x4": 18,
            "x2plus": 64, "x4plus": 64, "rife426": 24}

# 介面用模型名 → engine.models 的權重 key
WEIGHTS = {key: value[0] for key, value in MODEL_CHOICES.items()}
WEIGHTS["rife426"] = "rife426"


class _Downloader(QThread):
    progress = Signal(str, int, int)
    failed = Signal(str)
    all_done = Signal()

    def __init__(self, names: list[str], dest: str):
        super().__init__()
        self._names = names
        self._dest = dest

    def run(self) -> None:
        from engine.models import ensure_model

        for name in self._names:
            try:
                ensure_model(WEIGHTS[name], self._dest,
                             lambda done, total, n=name: self.progress.emit(n, done, total))
            except Exception:  # noqa: BLE001
                self.failed.emit(name)
            else:
                self.progress.emit(name, 1, 1)
        self.all_done.emit()


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("wizard.title"))
        self.setModal(True)
        self.resize(700, 580)
        self._info = backend.describe()
        self._checks: dict[str, QCheckBox] = {}
        self._bars: dict[str, QProgressBar] = {}
        self._labels: dict[str, QLabel] = {}
        self._worker: _Downloader | None = None
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        apply_dwm_chrome(int(self.winId()))

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)

        self._step = QLabel()
        self._step.setObjectName("hint")
        outer.addWidget(self._step)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        self._stack.addWidget(self._scan_page())
        self._stack.addWidget(self._models_page())
        self._stack.addWidget(self._download_page())

        row = QHBoxLayout()
        row.addStretch(1)
        self._back = QPushButton(tr("wizard.back"))
        self._back.setObjectName("ghost")
        self._back.clicked.connect(self._go_back)
        self._next = QPushButton(tr("wizard.next"))
        self._next.setObjectName("primary")
        self._next.clicked.connect(self._go_next)
        self._close = QPushButton(tr("wizard.close"))
        self._close.setObjectName("ghost")
        self._close.clicked.connect(self.reject)
        row.addWidget(self._back)
        row.addWidget(self._next)
        row.addWidget(self._close)
        outer.addLayout(row)

        self._sync_page()

    def _scan_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(12)

        title = QLabel(tr("wizard.scan.title"))
        title.setObjectName("appTitle")
        box.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(8)
        gpu = self._info.get("gpu") or tr("wizard.scan.not_found")
        pairs = [
            (tr("wizard.scan.gpu"), gpu),
            (tr("wizard.scan.vram"),
             f"{self._info['vram_gb']} GB" if self._info.get("vram_gb") else tr("wizard.scan.not_found")),
            (tr("wizard.scan.cpu"), str(self._info.get("cpu_cores") or "-")),
            (tr("wizard.scan.ram"),
             f"{self._info['ram_gb']} GB" if self._info.get("ram_gb") else tr("wizard.scan.not_found")),
            (tr("wizard.scan.disk"),
             f"{self._info['disk_free_gb']} GB" if self._info.get("disk_free_gb") else tr("wizard.scan.not_found")),
            (tr("wizard.scan.ffmpeg"), pathlib.Path(self._info["ffmpeg"]).name),
            ("ffprobe", pathlib.Path(self._info["ffprobe"]).name),
        ]
        for label, value in pairs:
            form.addRow(label, QLabel(value))

        box.addLayout(form)
        box.addStretch(1)

        self._unsupported = QLabel()
        self._unsupported.setWordWrap(True)
        self._unsupported.setObjectName("status")
        box.addWidget(self._unsupported)

        self._tile_hint = QLabel()
        self._tile_hint.setObjectName("hint")
        box.addWidget(self._tile_hint)
        return page

    def _models_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(10)
        title = QLabel(tr("wizard.models.title"))
        title.setObjectName("appTitle")
        box.addWidget(title)
        hint = QLabel(tr("wizard.models.hint"))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        box.addWidget(hint)

        total = sum(SIZES_MB[n] for n in ORDER)
        box.addWidget(QLabel(tr("wizard.models.total", size=total)))

        for name in ORDER:
            check = QCheckBox(f"{tr(f'wizard.model.{name}')}  ·  {SIZES_MB[name]} MB")
            check.setChecked(True)
            check.stateChanged.connect(self._sync_page)
            self._checks[name] = check
            box.addWidget(check)
        box.addStretch(1)
        return page

    def _download_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(10)
        title = QLabel(tr("wizard.download.title"))
        title.setObjectName("appTitle")
        box.addWidget(title)
        for name in ORDER:
            label = QLabel(tr(f"wizard.model.{name}"))
            label.setObjectName("field")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            self._bars[name] = bar
            self._labels[name] = label
            box.addWidget(label)
            box.addWidget(bar)
        self._download_status = QLabel("")
        self._download_status.setObjectName("hint")
        self._download_status.setWordWrap(True)
        box.addWidget(self._download_status)
        box.addStretch(1)
        return page

    def _selected(self) -> list[str]:
        return [name for name in ORDER if self._checks[name].isChecked()]

    def _sync_page(self) -> None:
        index = self._stack.currentIndex()
        self._step.setText(tr("wizard.step", current=index + 1, total=3))
        self._back.setEnabled(index > 0 and self._worker is None)
        self._close.setVisible(index == 0)
        self._next.setVisible(index < 2)
        if index == 0:
            supported = self._info["vendor"] in ("nvidia", "amd")
            tools_ok = self._info["media_tools_ok"]
            self._next.setEnabled(supported and tools_ok)
            messages = []
            if not supported:
                messages.append(tr("wizard.unsupported.body"))
            if not tools_ok:
                messages.append(tr("wizard.tools_missing"))
            self._unsupported.setText("\n".join(messages))
            self._close.setText(tr("wizard.close"))
            if supported:
                tile = tile_for_vram(768, self._info.get("vram_gb"))
                self._tile_hint.setText(tr("wizard.scan.tile", tile=tile))
        elif index == 1:
            self._next.setEnabled(bool(self._selected()))
        else:
            self._next.setEnabled(False)

    def _go_back(self) -> None:
        self._stack.setCurrentIndex(self._stack.currentIndex() - 1)
        self._sync_page()

    def _go_next(self) -> None:
        index = self._stack.currentIndex()
        if index == 0:
            self._stack.setCurrentIndex(1)
            self._sync_page()
            return
        if index == 1:
            names = self._selected()
            for name in ORDER:
                self._bars[name].setVisible(name in names)
                self._labels[name].setVisible(name in names)
            self._stack.setCurrentIndex(2)
            self._worker = _Downloader(names, config.models_dir())
            self._worker.progress.connect(self._on_progress)
            self._worker.failed.connect(self._on_failed)
            self._worker.all_done.connect(self._on_all_done)
            self._worker.start()
            self._sync_page()

    def _on_progress(self, name: str, done: int, total: int) -> None:
        pct = 100 if not total else min(100, int(done * 100 / total))
        self._bars[name].setValue(pct)

    def _on_failed(self, name: str) -> None:
        self._download_status.setText(tr("wizard.download.failed", name=name))

    def _on_all_done(self) -> None:
        config.mark_setup_done()
        self._download_status.setText(tr("wizard.download.done"))
        self._next.setVisible(True)
        self._next.setText(tr("wizard.finish"))
        self._next.setEnabled(True)
        self._next.clicked.disconnect()
        self._next.clicked.connect(self.accept)
