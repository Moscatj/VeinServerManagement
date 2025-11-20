"""
KVRow widget for config editor entries.
"""

from __future__ import annotations

from typing import Any, Tuple

from PySide6 import QtCore, QtGui, QtWidgets


class KVRow(QtWidgets.QWidget):
    changed = QtCore.Signal(tuple, object)

    def __init__(self, label: str, path: Tuple[str, ...], value: Any, parent=None):
        super().__init__(parent)
        self.path = path
        self.label_text = label
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)
        lab = QtWidgets.QLabel(label)
        lab.setMinimumWidth(180)
        h.addWidget(lab)
        self.label = lab
        if isinstance(value, bool):
            w = QtWidgets.QCheckBox()
            w.setChecked(value)
            w.stateChanged.connect(
                lambda *_: self.changed.emit(self.path, bool(w.isChecked()))
            )
            editor = w
        elif isinstance(value, int) and not isinstance(value, bool):
            w = QtWidgets.QLineEdit(str(value))
            w.setValidator(QtGui.QIntValidator(-2_147_483_648, 2_147_483_647))
            w.editingFinished.connect(
                lambda: self.changed.emit(self.path, int(w.text() or 0))
            )
            editor = w
        elif isinstance(value, float):
            w = QtWidgets.QLineEdit(str(value))
            w.setValidator(
                QtGui.QDoubleValidator(bottom=-1e308, top=1e308, decimals=12)
            )
            w.editingFinished.connect(
                lambda: self.changed.emit(self.path, float(w.text() or 0.0))
            )
            editor = w
        else:
            box = QtWidgets.QWidget()
            hb = QtWidgets.QHBoxLayout(box)
            hb.setContentsMargins(0, 0, 0, 0)
            w = QtWidgets.QLineEdit("" if value is None else str(value))
            hb.addWidget(w, 1)
            key = self.path[-1] if self.path else ""

            def looks_path_key(k: str) -> bool:
                k = k.lower()
                return any(t in k for t in ("path", "file", "dir", "folder"))

            def is_dir_key(k: str) -> bool:
                k = k.lower()
                return "dir" in k or "folder" in k

            if looks_path_key(key):
                btn = QtWidgets.QToolButton()
                btn.setText("…")
                btn.setToolTip("Browse")

                def pick():
                    cur = w.text().strip() or str(QtCore.QDir.homePath())
                    if is_dir_key(key):
                        d = QtWidgets.QFileDialog.getExistingDirectory(
                            self, "Select folder", cur
                        )
                        if d:
                            w.setText(d)
                            self.changed.emit(self.path, d)
                    else:
                        p, _ = QtWidgets.QFileDialog.getOpenFileName(
                            self, "Select file", cur, "All files (*.*)"
                        )
                        if p:
                            w.setText(p)
                            self.changed.emit(self.path, p)

                btn.clicked.connect(pick)
                hb.addWidget(btn, 0)
            w.editingFinished.connect(lambda: self.changed.emit(self.path, w.text()))
            editor = box
        editor.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        h.addWidget(editor)
        self.editor = editor

    def value(self):
        if isinstance(self.editor, QtWidgets.QCheckBox):
            return bool(self.editor.isChecked())
        edits = self.editor.findChildren(QtWidgets.QLineEdit) or (
            [self.editor] if isinstance(self.editor, QtWidgets.QLineEdit) else []
        )
        if edits:
            return edits[0].text()
        return None

    def scrollToMe(self):
        self.setFocus()

    def set_value(self, value: Any):
        if isinstance(self.editor, QtWidgets.QCheckBox):
            self.editor.blockSignals(True)
            self.editor.setChecked(bool(value))
            self.editor.blockSignals(False)
        else:
            edits = self.editor.findChildren(QtWidgets.QLineEdit) or (
                [self.editor] if isinstance(self.editor, QtWidgets.QLineEdit) else []
            )
            if edits:
                e = edits[0]
                e.blockSignals(True)
                e.setText("" if value is None else str(value))
                e.blockSignals(False)

