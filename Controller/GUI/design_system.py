"""Shared visual primitives for a consistent Vein Manager interface."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


PAGE_MARGIN = 16
SECTION_SPACING = 12
CONTROL_SPACING = 8

BUTTON_PRIMARY = "primary"
BUTTON_SECONDARY = "secondary"
BUTTON_DANGER = "danger"
BUTTON_QUIET = "quiet"

NOTICE_INFO = "info"
NOTICE_SUCCESS = "success"
NOTICE_WARNING = "warning"
NOTICE_ERROR = "error"


def _refresh_style(widget: QtWidgets.QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_button_role(button: QtWidgets.QAbstractButton, role: str) -> None:
    """Assign a semantic role used by the targeted application stylesheet."""
    button.setProperty("buttonRole", role)
    _refresh_style(button)


class PageHeader(QtWidgets.QWidget):
    """Consistent page title and optional explanatory subtitle."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("pageHeader", True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(3)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setProperty("pageTitle", True)
        layout.addWidget(self.title_label)

        self.subtitle_label = QtWidgets.QLabel(subtitle)
        self.subtitle_label.setProperty("pageSubtitle", True)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        layout.addWidget(self.subtitle_label)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))


class InlineNotice(QtWidgets.QLabel):
    """Word-wrapped message banner with a semantic information level."""

    def __init__(self, text: str = "", kind: str = NOTICE_INFO, parent=None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        self.setProperty("noticeKind", kind)
        _refresh_style(self)


class StatusBadge(QtWidgets.QLabel):
    """Compact textual state indicator that does not rely on color alone."""

    def __init__(self, text: str, state: str = "neutral", parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.set_state(state, text)

    def set_state(self, state: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("statusState", state)
        _refresh_style(self)


def application_stylesheet() -> str:
    """Return palette-friendly styling limited to semantic GUI properties."""
    return """
        QWidget[pageHeader="true"] { background: transparent; }
        QLabel[pageTitle="true"] { font-size: 20px; font-weight: 700; }
        QLabel[pageSubtitle="true"] { color: palette(text); }

        QLabel[noticeKind] {
            border: 1px solid palette(mid);
            border-radius: 6px;
            padding: 8px 10px;
            background: palette(alternate-base);
        }
        QLabel[noticeKind="success"] { border-color: #2e8b57; }
        QLabel[noticeKind="warning"] { border-color: #c58a00; }
        QLabel[noticeKind="error"] { border-color: #c43d3d; }

        QLabel[statusState] {
            border-radius: 8px;
            padding: 2px 8px;
            font-weight: 600;
        }
        QLabel[statusState="healthy"] { background: #246b45; color: white; }
        QLabel[statusState="warning"] { background: #8a6200; color: white; }
        QLabel[statusState="error"] { background: #8f3030; color: white; }
        QLabel[statusState="neutral"] { background: palette(midlight); }

        QPushButton[buttonRole="primary"] {
            background: palette(highlight);
            color: palette(highlighted-text);
            font-weight: 600;
            padding: 6px 12px;
        }
        QPushButton[buttonRole="danger"] { color: #d84a4a; font-weight: 600; }
        QPushButton[buttonRole="quiet"] { padding: 4px 8px; }
    """


def apply_design_system(widget: QtWidgets.QWidget) -> None:
    """Apply shared targeted styling without replacing the active Qt palette."""
    widget.setStyleSheet(application_stylesheet())
