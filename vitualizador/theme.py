"""Tema escuro do Termux Lab."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Paleta base (estilo GitHub dark, com verde de terminal)
BG = "#0d1117"
BG_ALT = "#161b22"
BG_SURF = "#21262d"
BORDER = "#30363d"
TEXT = "#c9d1d9"
TEXT_DIM = "#8b949e"
GREEN = "#7ee787"
GREEN_DARK = "#238636"
GREEN_HOVER = "#2ea043"
BLUE = "#58a6ff"
ORANGE = "#f0883e"

_STYLE = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; }}
QLabel {{ background: transparent; }}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {GREEN};
}}
QPushButton {{
    background: {BG_SURF};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {BORDER}; border-color: #484f58; }}
QPushButton:pressed {{ background: {BG_ALT}; }}
QPushButton:disabled {{ color: #484f58; border-color: #21262d; background: {BG}; }}
QPushButton#primario {{
    background: {GREEN_DARK};
    border: 1px solid {GREEN_HOVER};
    color: #ffffff;
    font-weight: bold;
}}
QPushButton#primario:hover {{ background: {GREEN_HOVER}; }}
QPushButton#primario:disabled {{ background: #1b2a1d; color: #57606a; border-color: #1b2a1d; }}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: {GREEN_DARK};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {GREEN_HOVER};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QPlainTextEdit:disabled {{
    color: #57606a;
    background: {BG_ALT};
}}
QComboBox QAbstractItemView {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    selection-background-color: {GREEN_DARK};
    selection-color: #ffffff;
    outline: none;
}}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 8px 16px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:hover {{ color: {TEXT}; background: {BG_ALT}; }}
QTabBar::tab:selected {{
    color: {GREEN};
    background: {BG};
    border: 1px solid {BORDER};
    border-bottom-color: {BG};
}}
QListWidget, QTableWidget {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    alternate-background-color: #10151b;
    outline: none;
}}
QListWidget::item {{ padding: 6px; border-radius: 4px; }}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {GREEN_DARK};
    color: #ffffff;
}}
QHeaderView::section {{
    background: {BG_SURF};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 5px;
}}
QTableWidget {{ gridline-color: {BORDER}; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:hover {{ background: {GREEN_HOVER}; }}
QStatusBar {{ color: {TEXT_DIM}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background: {BG_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QScrollBar:vertical {{ background: {BG}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{ background: #484f58; }}
QScrollBar:horizontal {{ background: {BG}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 24px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover {{ background: #484f58; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QMenu {{ background: {BG_ALT}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {GREEN_DARK}; }}
QSpinBox {{ padding-right: 20px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 18px;
    background: {BG_SURF};
    border-left: 1px solid {BORDER};
}}
QSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 6px;
    border-bottom: 1px solid {BORDER};
}}
QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 6px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {BORDER}; }}
QSpinBox::up-arrow {{ image: url("__UP_ARROW__"); width: 9px; height: 9px; }}
QSpinBox::down-arrow {{ image: url("__DOWN_ARROW__"); width: 9px; height: 9px; }}
"""


def _assets() -> tuple[str, str]:
    """SVGs pequenos para as setas do QSpinBox (QSS não desenha sem imagem)."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "termux-lab"
    base.mkdir(parents=True, exist_ok=True)
    up = base / "seta-cima.svg"
    down = base / "seta-baixo.svg"
    if not up.exists():
        up.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' "
            "viewBox='0 0 12 12'><path d='M2.5 7.5 L6 4 L9.5 7.5' fill='none' "
            "stroke='#8b949e' stroke-width='1.8' stroke-linecap='round' "
            "stroke-linejoin='round'/></svg>", encoding="utf-8")
    if not down.exists():
        down.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' "
            "viewBox='0 0 12 12'><path d='M2.5 4.5 L6 8 L9.5 4.5' fill='none' "
            "stroke='#8b949e' stroke-width='1.8' stroke-linecap='round' "
            "stroke-linejoin='round'/></svg>", encoding="utf-8")
    return up.as_posix(), down.as_posix()


def style_sheet() -> str:
    up, down = _assets()
    return _STYLE.replace("__UP_ARROW__", up).replace("__DOWN_ARROW__", down)


def apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(BG))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_ALT))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ALT))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(BG_SURF))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ff7b72"))
    pal.setColor(QPalette.ColorRole.Link, QColor(BLUE))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(GREEN_DARK))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6e7681"))

    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#57606a"))

    app.setPalette(pal)
    app.setStyleSheet(style_sheet())
