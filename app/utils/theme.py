"""
Модуль темы и цветовой схемы приложения SecureSysAdmin.
Поддерживает тёмную и светлую темы, совместимые с WinPE/WinRE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class ColorPalette:
    """Набор цветов для одной темы."""
    name: str

    # Фон
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str
    bg_widget: str
    bg_hover: str
    bg_selected: str
    bg_disabled: str

    # Текст
    text_primary: str
    text_secondary: str
    text_disabled: str
    text_accent: str

    # Акценты / бренд
    accent_primary: str
    accent_secondary: str
    accent_hover: str
    accent_pressed: str

    # Статусы
    success: str
    warning: str
    danger: str
    info: str

    # Границы / разделители
    border: str
    border_focus: str
    divider: str

    # Таб-бар
    tab_active_bg: str
    tab_inactive_bg: str
    tab_active_text: str
    tab_inactive_text: str
    tab_indicator: str

    # Скроллбар
    scrollbar_bg: str
    scrollbar_handle: str
    scrollbar_handle_hover: str

    # Прогресс-бар
    progress_bg: str
    progress_chunk: str

    # Специальные
    terminal_bg: str
    terminal_text: str
    menu_bg: str
    menu_text: str
    tooltip_bg: str
    tooltip_text: str

    # QSS
    extra_qss: str = ""


# ── ТЁМНАЯ ТЕМА (по умолчанию) ─────────────────────────────────────────────
DARK_PALETTE = ColorPalette(
    name="dark",
    # Фон
    bg_primary="#1a1d23",
    bg_secondary="#21252b",
    bg_tertiary="#282c34",
    bg_widget="#2c313a",
    bg_hover="#353b48",
    bg_selected="#3a3f4b",
    bg_disabled="#252830",

    # Текст
    text_primary="#e1e4e8",
    text_secondary="#959da5",
    text_disabled="#586069",
    text_accent="#79b8ff",

    # Акценты
    accent_primary="#58a6ff",
    accent_secondary="#3b8fef",
    accent_hover="#79b8ff",
    accent_pressed="#2f7fdf",

    # Статусы
    success="#34d058",
    warning="#d29922",
    danger="#f85149",
    info="#58a6ff",

    # Границы
    border="#3a3f4b",
    border_focus="#58a6ff",
    divider="#2a2e36",

    # Таб-бар
    tab_active_bg="#1a1d23",
    tab_inactive_bg="#21252b",
    tab_active_text="#e1e4e8",
    tab_inactive_text="#959da5",
    tab_indicator="#58a6ff",

    # Скроллбар
    scrollbar_bg="#1a1d23",
    scrollbar_handle="#3a3f4b",
    scrollbar_handle_hover="#4a4f5b",

    # Прогресс-бар
    progress_bg="#2c313a",
    progress_chunk="#58a6ff",

    # Специальные
    terminal_bg="#0d1117",
    terminal_text="#c9d1d9",
    menu_bg="#2c313a",
    menu_text="#e1e4e8",
    tooltip_bg="#2c313a",
    tooltip_text="#e1e4e8",
)


# ── СВЕТЛАЯ ТЕМА ───────────────────────────────────────────────────────────
LIGHT_PALETTE = ColorPalette(
    name="light",
    # Фон
    bg_primary="#ffffff",
    bg_secondary="#f6f8fa",
    bg_tertiary="#eef1f5",
    bg_widget="#f0f2f5",
    bg_hover="#e4e8ed",
    bg_selected="#dde4ee",
    bg_disabled="#f0f2f5",

    # Текст
    text_primary="#24292e",
    text_secondary="#586069",
    text_disabled="#959da5",
    text_accent="#0366d6",

    # Акценты
    accent_primary="#0366d6",
    accent_secondary="#0250b3",
    accent_hover="#1478e6",
    accent_pressed="#0249a8",

    # Статусы
    success="#28a745",
    warning="#b08800",
    danger="#d73a49",
    info="#0366d6",

    # Границы
    border="#d1d5da",
    border_focus="#0366d6",
    divider="#e1e4e8",

    # Таб-бар
    tab_active_bg="#ffffff",
    tab_inactive_bg="#f6f8fa",
    tab_active_text="#24292e",
    tab_inactive_text="#586069",
    tab_indicator="#0366d6",

    # Скроллбар
    scrollbar_bg="#f6f8fa",
    scrollbar_handle="#d1d5da",
    scrollbar_handle_hover="#b1b5ba",

    # Прогресс-бар
    progress_bg="#eef1f5",
    progress_chunk="#0366d6",

    # Специальные
    terminal_bg="#f6f8fa",
    terminal_text="#24292e",
    menu_bg="#ffffff",
    menu_text="#24292e",
    tooltip_bg="#24292e",
    tooltip_text="#ffffff",
)

PALETTES: Dict[str, ColorPalette] = {
    "dark": DARK_PALETTE,
    "light": LIGHT_PALETTE,
}


def _rgba(hex_color: str, alpha: int) -> str:
    """Преобразует HEX в rgba(...) с указанной альфой (0–255)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def build_stylesheet(p: ColorPalette, font_family: str = "Segoe UI") -> str:
    """
    Собирает полную QSS-таблицу стилей на основе палитры.
    Совместима с PyQt6.
    """
    return f"""
/* ================================================================
   SecureSysAdmin — автоматически сгенерированный QSS
   Тема: {p.name}
   ================================================================ */

/* ── Глобальные ─────────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {p.bg_primary};
}}

* {{
    color: {p.text_primary};
    font-family: "{font_family}";
    font-size: 13px;
}}

/* ── QLabel ─────────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {p.text_primary};
    border: none;
}}

QLabel[heading="true"] {{
    font-size: 16px;
    font-weight: bold;
    color: {p.text_primary};
}}

QLabel[subheading="true"] {{
    font-size: 13px;
    color: {p.text_secondary};
}}

/* ── QPushButton ────────────────────────────────────────────────── */
QPushButton {{
    background-color: {p.bg_widget};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {p.bg_hover};
    border-color: {p.accent_primary};
}}

QPushButton:pressed {{
    background-color: {p.bg_selected};
    border-color: {p.accent_pressed};
}}

QPushButton:disabled {{
    background-color: {p.bg_disabled};
    color: {p.text_disabled};
    border-color: {p.border};
}}

QPushButton[accent="true"] {{
    background-color: {p.accent_primary};
    color: #ffffff;
    border: none;
    font-weight: bold;
}}

QPushButton[accent="true"]:hover {{
    background-color: {p.accent_hover};
}}

QPushButton[accent="true"]:pressed {{
    background-color: {p.accent_pressed};
}}

QPushButton[danger="true"] {{
    background-color: {p.danger};
    color: #ffffff;
    border: none;
    font-weight: bold;
}}

QPushButton[small="true"] {{
    padding: 4px 10px;
    font-size: 12px;
    min-height: 16px;
}}

/* ── QLineEdit / QTextEdit / QPlainTextEdit ─────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {p.bg_tertiary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: {p.accent_primary};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {p.border_focus};
}}

/* ── QComboBox ───────────────────────────────────────────────────── */
QComboBox {{
    background-color: {p.bg_widget};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 100px;
}}

QComboBox:hover {{
    border-color: {p.accent_primary};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
}}

QComboBox QAbstractItemView {{
    background-color: {p.menu_bg};
    color: {p.menu_text};
    selection-background-color: {p.accent_primary};
    selection-color: #ffffff;
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px;
    outline: none;
}}

/* ── QCheckBox / QRadioButton ───────────────────────────────────── */
QCheckBox, QRadioButton {{
    background: transparent;
    color: {p.text_primary};
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.border};
    border-radius: 3px;
    background-color: {p.bg_tertiary};
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {p.accent_primary};
    border-color: {p.accent_primary};
}}

/* ── QTabWidget / QTabBar ───────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background-color: {p.bg_primary};
}}

QTabBar::tab {{
    background-color: {p.tab_inactive_bg};
    color: {p.tab_inactive_text};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 20px;
    margin-right: 2px;
    font-size: 13px;
    min-width: 90px;
}}

QTabBar::tab:hover {{
    background-color: {p.bg_hover};
    color: {p.text_primary};
}}

QTabBar::tab:selected {{
    background-color: {p.tab_active_bg};
    color: {p.tab_active_text};
    border-bottom: 2px solid {p.tab_indicator};
    font-weight: bold;
}}

/* ── QTreeView / QListView / QTableView ─────────────────────────── */
QTreeView, QListView, QTableView {{
    background-color: {p.bg_secondary};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 4px;
    alternate-background-color: {p.bg_tertiary};
    selection-background-color: {p.accent_primary};
    selection-color: #ffffff;
    outline: none;
    gridline-color: {p.divider};
}}

QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {{
    background-color: {p.bg_hover};
}}

QHeaderView::section {{
    background-color: {p.bg_tertiary};
    color: {p.text_secondary};
    border: none;
    border-bottom: 1px solid {p.border};
    border-right: 1px solid {p.divider};
    padding: 6px 10px;
    font-weight: bold;
    font-size: 12px;
}}

/* ── QScrollBar ──────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {p.scrollbar_bg};
    width: 10px;
    border: none;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {p.scrollbar_handle};
    min-height: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.scrollbar_handle_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {p.scrollbar_bg};
    height: 10px;
    border: none;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {p.scrollbar_handle};
    min-width: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {p.scrollbar_handle_hover};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── QProgressBar ────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {p.progress_bg};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    font-size: 11px;
    color: {p.text_primary};
}}

QProgressBar::chunk {{
    background-color: {p.progress_chunk};
    border-radius: 4px;
}}

/* ── QMenu ───────────────────────────────────────────────────────── */
QMenu {{
    background-color: {p.menu_bg};
    color: {p.menu_text};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {p.accent_primary};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: {p.divider};
    margin: 4px 8px;
}}

/* ── QToolTip ────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {p.tooltip_bg};
    color: {p.tooltip_text};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── QSplitter ───────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {p.border};
    margin: 1px;
}}

QSplitter::handle:horizontal {{
    width: 3px;
}}

QSplitter::handle:vertical {{
    height: 3px;
}}

/* ── QGroupBox ───────────────────────────────────────────────────── */
QGroupBox {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 6px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    color: {p.text_primary};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {p.text_secondary};
}}

/* ── Дополнительные ──────────────────────────────────────────────── */
{p.extra_qss}
"""


# Экспорт для удобного импорта
__all__ = [
    "ColorPalette",
    "DARK_PALETTE",
    "LIGHT_PALETTE",
    "PALETTES",
    "build_stylesheet",
]