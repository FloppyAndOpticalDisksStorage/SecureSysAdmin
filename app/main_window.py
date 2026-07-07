"""
Главное окно SecureSysAdmin.
Объединяет все вкладки: сканер, быстрые действия, проводник, диспетчер задач, настройки.
"""
from __future__ import annotations

import os
import sys
from functools import partial
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QSize,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QStatusBar, QMessageBox,
    QApplication, QStackedWidget, QFrame, QProgressBar,
    QFileDialog, QSplitter, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMenu, QAbstractItemView, QGroupBox,
    QTextEdit, QLineEdit, QComboBox,
)
from PyQt6.QtGui import QIcon, QAction, QFont, QFontDatabase

from app.utils.theme import (
    ColorPalette, DARK_PALETTE, LIGHT_PALETTE, PALETTES,
    build_stylesheet,
)
from app.utils.animations import (
    set_animations_enabled, animations_enabled,
    fade_in, tab_switch_animation, pulse,
)
from app.scanner.virus_scanner import (
    VirusScanner, FileRemediator, ScanResult, ThreatLevel,
)
from app.tabs.quick_actions import QuickActionsTab
from app.tabs.file_explorer import FileExplorerTab
from app.tabs.task_manager import TaskManagerTab
from app.tabs.settings import SettingsTab, AppSettings
from app.tabs.restrictions import RestrictionsTab


# ── Константы ──────────────────────────────────────────────────────────────
APP_NAME = "SecureSysAdmin"
APP_VERSION = "0.1"
ORG_NAME = "SecureSysAdmin"


class ScannerWorker(QThread):
    """Поток для фонового сканирования."""
    progress = pyqtSignal(ScanResult, int, int)  # result, scanned, total
    finished = pyqtSignal(list)
    status = pyqtSignal(str)

    def __init__(self, scanner: VirusScanner, directory: str, parent=None):
        super().__init__(parent)
        self.scanner = scanner
        self.directory = directory

    def run(self):
        self.status.emit(f"🔍 Сканирование: {self.directory}")
        results = self.scanner.scan_directory(
            self.directory,
            callback=lambda r, s, t: self.progress.emit(r, s, t),
        )
        self.finished.emit(results)

    def stop(self):
        self.scanner.stop()


class RedSidebar(QFrame):
    """Левый сайдбар с навигацией."""

    tab_selected = pyqtSignal(int)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._buttons: list[QPushButton] = []
        self._active_index = 0
        self._setup_ui()

    def _setup_ui(self):
        p = self._palette
        self.setFixedWidth(200)
        self.setStyleSheet(f"""
            RedSidebar {{
                background-color: {p.bg_secondary};
                border-right: 1px solid {p.border};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Логотип
        logo_frame = QFrame()
        logo_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_tertiary};
                border-bottom: 1px solid {p.border};
            }}
        """)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(16, 16, 16, 12)

        logo_title = QLabel("🛡 SecureSysAdmin")
        logo_title.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {p.text_primary}; border: none;"
        )
        logo_layout.addWidget(logo_title)

        ver = QLabel(f"v{APP_VERSION} — WinPE/RE Ready")
        ver.setStyleSheet(f"font-size: 10px; color: {p.text_secondary}; border: none;")
        logo_layout.addWidget(ver)

        layout.addWidget(logo_frame)

        # Кнопки навигации
        tabs_data = [
            ("🛡  Сканер", 0),
            ("⚡  Быстрые действия", 1),
            ("📁  Проводник", 2),
            ("📊  Диспетчер задач", 3),
            ("🔓  Ограничения", 4),
            ("⚙  Настройки", 5),
        ]

        for label, index in tabs_data:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 8px 16px;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0;
                    color: {p.text_secondary};
                    font-size: 13px;
                    background: transparent;
                }}
                QPushButton:hover {{
                    background-color: {p.bg_hover};
                    color: {p.text_primary};
                }}
                QPushButton:checked {{
                    background-color: {p.bg_selected};
                    color: {p.text_primary};
                    border-left: 3px solid {p.accent_primary};
                    font-weight: bold;
                }}
            """)
            btn.clicked.connect(lambda checked, i=index: self._on_tab_click(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Кнопка выхода внизу
        exit_btn = QPushButton("  🚪 Выход")
        exit_btn.setFixedHeight(44)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 8px 16px;
                border: none;
                border-radius: 0;
                color: {p.text_secondary};
                font-size: 13px;
                background: transparent;
            }}
            QPushButton:hover {{
                background-color: {p.bg_hover};
                color: {p.danger};
            }}
        """)
        exit_btn.clicked.connect(lambda: QApplication.instance().quit())
        layout.addWidget(exit_btn)

        # Выделяем первую кнопку
        self._buttons[0].setChecked(True)

    def _on_tab_click(self, index: int):
        self.set_active(index)
        self.tab_selected.emit(index)

    def set_active(self, index: int):
        if 0 <= index < len(self._buttons):
            self._buttons[self._active_index].setChecked(False)
            self._active_index = index
            self._buttons[index].setChecked(True)


class ScanResultTree(QTreeWidget):
    """Дерево результатов сканирования с контекстным меню."""

    delete_requested = pyqtSignal(str)
    quarantine_requested = pyqtSignal(str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self.setHeaderLabels([
            "Путь", "Уровень угрозы", "Причина", "MD5", "Размер"
        ])
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.setSortingEnabled(True)

        # Ширины колонок
        header = self.header()
        header.setStretchLastSection(False)
        self.setColumnWidth(0, 400)
        self.setColumnWidth(1, 130)
        self.setColumnWidth(2, 250)
        self.setColumnWidth(3, 260)
        self.setColumnWidth(4, 80)

    def add_result(self, result: ScanResult):
        item = QTreeWidgetItem()
        item.setText(0, result.path)
        item.setText(1, result.threat_level.name)
        item.setText(2, result.reason)
        item.setText(3, result.md5[:32] if result.md5 else "")
        item.setText(4, self._fmt_size(result.size))
        item.setData(0, Qt.ItemDataRole.UserRole, result.path)

        # Цвет строки
        colors = {
            ThreatLevel.SAFE.name: self._palette.success,
            ThreatLevel.SUSPICIOUS.name: self._palette.warning,
            ThreatLevel.HIGH.name: self._palette.danger,
            ThreatLevel.CRITICAL.name: self._palette.danger,
        }
        color = QColor(colors.get(result.threat_level.name, self._palette.text_primary))
        for col in range(5):
            item.setForeground(col, color)

        if result.threat_level != ThreatLevel.SAFE:
            item.setBackground(0, QColor(self._palette.bg_hover))

        self.addTopLevelItem(item)

    def clear_results(self):
        self.clear()

    def _context_menu(self, pos):
        items = self.selectedItems()
        if not items:
            return
        paths = [it.data(0, Qt.ItemDataRole.UserRole) for it in items]

        menu = QMenu(self)

        act_open = menu.addAction("📂 Открыть в проводнике")
        act_open.triggered.connect(lambda: self._open_in_explorer(paths[0]) if paths else None)

        menu.addSeparator()

        act_quarantine = menu.addAction("🔒 В карантин")
        act_quarantine.triggered.connect(lambda: [self.quarantine_requested.emit(p) for p in paths])

        act_delete = menu.addAction("🗑 Удалить")
        act_delete.triggered.connect(lambda: [self.delete_requested.emit(p) for p in paths])

        menu.addSeparator()

        act_copy = menu.addAction("📋 Копировать путь")
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText("\n".join(paths)))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _open_in_explorer(self, path: str):
        import subprocess
        if os.path.isdir(path):
            subprocess.Popen(["explorer.exe", path])
        else:
            subprocess.Popen(["explorer.exe", "/select,", path])

    @staticmethod
    def _fmt_size(size: int) -> str:
        for unit in ["Б", "КБ", "МБ", "ГБ"]:
            if abs(size) < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self._palette: ColorPalette = DARK_PALETTE
        self._current_theme = "dark"
        self._scanner = VirusScanner()
        self._scanner_worker: Optional[ScannerWorker] = None
        self._settings = AppSettings.load()

        # Применяем сохранённые настройки
        self._current_theme = self._settings.theme
        self._palette = PALETTES.get(self._current_theme, DARK_PALETTE)
        set_animations_enabled(self._settings.animations_enabled)

        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._connect_signals()


    # ── Настройка окна ─────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        self.setWindowIcon(QIcon())

        # Центрирование
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - self.width()) // 2,
                (geo.height() - self.height()) // 2,
            )

    # ── Построение UI ─────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Сайдбар ─────────────────────────────────────────────────
        self._sidebar = RedSidebar(self._palette)
        main_layout.addWidget(self._sidebar)

        # ── Правая панель: стек вкладок ──────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._stack = QStackedWidget()
        right_layout.addWidget(self._stack, 1)

        # ── Создание всех вкладок ────────────────────────────────────
        self._scanner_tab = self._create_scanner_tab()
        self._quick_tab = QuickActionsTab(self._palette)
        self._file_explorer_tab = FileExplorerTab(self._palette)
        self._task_manager_tab = TaskManagerTab(self._palette)
        self._restrictions_tab = RestrictionsTab(self._palette)
        self._settings_tab = SettingsTab(self._palette)

        self._stack.addWidget(self._scanner_tab)        # index 0
        self._stack.addWidget(self._quick_tab)           # index 1
        self._stack.addWidget(self._file_explorer_tab)   # index 2
        self._stack.addWidget(self._task_manager_tab)    # index 3
        self._stack.addWidget(self._restrictions_tab)    # index 4
        self._stack.addWidget(self._settings_tab)        # index 5

        main_layout.addWidget(right_panel)

        # ── Статус-бар ──────────────────────────────────────────────
        self._status = QStatusBar()
        self._status.setStyleSheet(f"""
            QStatusBar {{
                background-color: {self._palette.bg_tertiary};
                color: {self._palette.text_secondary};
                border-top: 1px solid {self._palette.border};
                font-size: 12px;
                padding: 2px 8px;
            }}
        """)
        self._status.showMessage("Готов | SecureSysAdmin — WinPE/WinRE Ready")
        self.setStatusBar(self._status)

    # ── Вкладка сканера (встроена в главное окно) ─────────────────────────

    def _create_scanner_tab(self) -> QWidget:
        """Создаёт вкладку сканера безопасности."""
        p = self._palette
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Заголовок
        title = QLabel("🛡 Сканер безопасности")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(title)

        subtitle = QLabel("Сканирование файлов на вирусы и подозрительную активность")
        subtitle.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        layout.addWidget(subtitle)

        # Панель управления сканированием
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
        """)
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(16, 12, 16, 12)
        ctrl_layout.setSpacing(10)

        # Строка: путь + кнопки
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Путь:"))
        self._scan_path = QLineEdit()
        self._scan_path.setText(self._settings.scan_default_path)
        self._scan_path.setPlaceholderText("C:\\ или выберите папку...")
        path_row.addWidget(self._scan_path, 1)

        browse_btn = QPushButton("📂 Обзор")
        browse_btn.setProperty("small", True)
        browse_btn.clicked.connect(self._browse_scan_path)
        path_row.addWidget(browse_btn)
        ctrl_layout.addLayout(path_row)

        # Кнопки управления
        btn_row = QHBoxLayout()

        self._scan_start_btn = QPushButton("▶ Начать сканирование")
        self._scan_start_btn.setProperty("accent", True)
        self._scan_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_start_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_start_btn)

        self._scan_stop_btn = QPushButton("⏹ Остановить")
        self._scan_stop_btn.setProperty("danger", True)
        self._scan_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_stop_btn.clicked.connect(self._stop_scan)
        self._scan_stop_btn.setEnabled(False)
        btn_row.addWidget(self._scan_stop_btn)

        self._scan_pause_btn = QPushButton("⏸ Пауза")
        self._scan_pause_btn.setProperty("small", True)
        self._scan_pause_btn.setEnabled(False)
        btn_row.addWidget(self._scan_pause_btn)

        btn_row.addStretch()

        self._scan_stats = QLabel("Готов к сканированию")
        self._scan_stats.setStyleSheet(f"color: {p.text_secondary};")
        btn_row.addWidget(self._scan_stats)

        ctrl_layout.addLayout(btn_row)

        # Прогресс-бар
        self._scan_progress = QProgressBar()
        self._scan_progress.setVisible(False)
        self._scan_progress.setMaximum(100)
        ctrl_layout.addWidget(self._scan_progress)

        layout.addWidget(ctrl_frame)

        # Результаты сканирования
        results_frame = QFrame()
        results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(0, 0, 0, 0)

        results_header = QHBoxLayout()
        results_label = QLabel("📋 Результаты сканирования")
        results_label.setStyleSheet(f"font-weight: bold; color: {p.text_primary};")
        results_header.addWidget(results_label)
        results_header.addStretch()

        # Сводка угроз
        self._threat_summary = QLabel("")
        self._threat_summary.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        results_header.addWidget(self._threat_summary)

        clear_btn = QPushButton("🗑 Очистить")
        clear_btn.setProperty("small", True)
        clear_btn.clicked.connect(self._clear_results)
        results_header.addWidget(clear_btn)

        # Кнопки массовых действий
        quarantine_all_btn = QPushButton("🔒 Всё в карантин")
        quarantine_all_btn.setProperty("small", True)
        quarantine_all_btn.clicked.connect(self._quarantine_all_threats)
        results_header.addWidget(quarantine_all_btn)

        delete_all_btn = QPushButton("🗑 Удалить все угрозы")
        delete_all_btn.setProperty("small", True)
        delete_all_btn.setProperty("danger", True)
        delete_all_btn.clicked.connect(self._delete_all_threats)
        results_header.addWidget(delete_all_btn)

        results_layout.addLayout(results_header)

        self._results_tree = ScanResultTree(self._palette)
        self._results_tree.delete_requested.connect(self._delete_file)
        self._results_tree.quarantine_requested.connect(self._quarantine_file)
        results_layout.addWidget(self._results_tree, 1)

        layout.addWidget(results_frame, 1)

        return tab

    # ── Сигналы ────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._sidebar.tab_selected.connect(self._on_tab_changed)
        self._settings_tab.theme_changed.connect(self._on_theme_changed)
        self._settings_tab.settings_changed.connect(self._on_settings_changed)
        self._settings_tab.status_message.connect(self._show_status)

        # Статус-сообщения от вкладок
        self._quick_tab.execute_command.connect(self._on_quick_command)
        self._file_explorer_tab.status_message.connect(self._show_status)
        self._task_manager_tab.status_message.connect(self._show_status)
        self._restrictions_tab.status_message.connect(self._show_status)

    def _on_quick_command(self, label: str, command: str):
        """Обработчик команд от вкладки быстрых действий."""
        self._show_status(f"Выполняется: {label} — {command}")

    def _on_tab_changed(self, index: int):
        """Переключение вкладки."""
        self._stack.setCurrentIndex(index)
        tab_names = [
            "Сканер безопасности",
            "Быстрые действия",
            "Файловый проводник",
            "Диспетчер задач",
            "Ограничения и дебаггеры",
            "Настройки",
        ]
        self._show_status(f"Вкладка: {tab_names[index] if 0 <= index < len(tab_names) else ''}")

    def _on_theme_changed(self, theme_name: str):
        """Мгновенное переключение темы при выборе в настройках."""
        self._current_theme = theme_name
        self._palette = PALETTES.get(theme_name, DARK_PALETTE)
        self._apply_theme()

    def _on_settings_changed(self, settings: AppSettings):
        """Применяет изменённые настройки."""
        self._settings = settings
        self._current_theme = settings.theme
        self._palette = PALETTES.get(settings.theme, DARK_PALETTE)
        set_animations_enabled(settings.animations_enabled)
        self._apply_theme()
        self._scan_path.setText(settings.scan_default_path)

    def _apply_theme(self):
        """Применяет QSS таблицу стилей ко всему приложению."""
        stylesheet = build_stylesheet(self._palette, "Segoe UI")
        QApplication.instance().setStyleSheet(stylesheet)

        # Обновляем статус-бар (он re-created)
        if hasattr(self, '_status'):
            self._status.setStyleSheet(f"""
                QStatusBar {{
                    background-color: {self._palette.bg_tertiary};
                    color: {self._palette.text_secondary};
                    border-top: 1px solid {self._palette.border};
                    font-size: 12px;
                }}
            """)

    # ── Сканирование ───────────────────────────────────────────────────────

    def _browse_scan_path(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку для сканирования")
        if path:
            self._scan_path.setText(path)

    def _start_scan(self):
        path = self._scan_path.text().strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Ошибка", "Укажите корректный путь для сканирования.")
            return

        self._scanner.reset()
        self._results_tree.clear_results()
        self._scan_progress.setVisible(True)
        self._scan_progress.setValue(0)
        self._scan_start_btn.setEnabled(False)
        self._scan_stop_btn.setEnabled(True)
        self._scan_pause_btn.setEnabled(False)

        self._scanner_worker = ScannerWorker(self._scanner, path)
        self._scanner_worker.progress.connect(self._on_scan_progress)
        self._scanner_worker.finished.connect(self._on_scan_finished)
        self._scanner_worker.status.connect(self._show_status)
        self._scanner_worker.start()

    def _stop_scan(self):
        if self._scanner_worker:
            self._scanner_worker.stop()
            self._show_status("⏹ Сканирование остановлено пользователем")

    def _on_scan_progress(self, result: ScanResult, scanned: int, total: int):
        self._results_tree.add_result(result)
        if total > 0:
            pct = int(scanned * 100 / total)
            self._scan_progress.setValue(pct)
        self._scan_stats.setText(
            f"Просканировано: {scanned}/{total} | "
            f"Угроз: {self._scanner.threats_found} | "
            f"⏱ {self._scanner.elapsed_seconds:.1f}с"
        )

    def _on_scan_finished(self, results: list):
        self._scan_start_btn.setEnabled(True)
        self._scan_stop_btn.setEnabled(False)
        self._scan_progress.setVisible(False)

        threat_count = self._scanner.threats_found
        total = len(results)

        if threat_count == 0:
            self._threat_summary.setText("✅ Угроз не обнаружено")
            self._threat_summary.setStyleSheet(
                f"color: {self._palette.success}; font-size: 12px; font-weight: bold;"
            )
        else:
            self._threat_summary.setText(f"⚠ Найдено угроз: {threat_count}")
            self._threat_summary.setStyleSheet(
                f"color: {self._palette.danger}; font-size: 12px; font-weight: bold;"
            )

        self._show_status(
            f"✅ Сканирование завершено за {self._scanner.elapsed_seconds:.1f}с. "
            f"Файлов: {total}, угроз: {threat_count}"
        )

    def _clear_results(self):
        self._results_tree.clear_results()
        self._scanner.reset()
        self._threat_summary.setText("")
        self._scan_progress.setVisible(False)
        self._scan_progress.setValue(0)
        self._scan_stats.setText("Готов к сканированию")
        self._show_status("Результаты очищены")

    # ── Действия над файлами ───────────────────────────────────────────────

    def _delete_file(self, filepath: str):
        success = FileRemediator.delete(filepath)
        if success:
            self._show_status(f"🗑 Удалён: {filepath}")
        else:
            self._show_status(f"❌ Не удалось удалить: {filepath}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить файл:\n{filepath}")

    def _quarantine_file(self, filepath: str):
        success = FileRemediator.quarantine(filepath)
        if success:
            self._show_status(f"🔒 В карантин: {filepath}")
        else:
            self._show_status(f"❌ Не удалось переместить в карантин: {filepath}")
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось переместить в карантин:\n{filepath}")

    def _quarantine_all_threats(self):
        threats = [
            r for r in self._scanner.results
            if r.threat_level != ThreatLevel.SAFE
        ]
        if not threats:
            self._show_status("Нет угроз для карантина")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Переместить {len(threats)} файлов в карантин?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        count = 0
        for r in threats:
            if FileRemediator.quarantine(r.path):
                count += 1
        self._show_status(f"🔒 В карантин: {count}/{len(threats)}")

    def _delete_all_threats(self):
        threats = [
            r for r in self._scanner.results
            if r.threat_level != ThreatLevel.SAFE
        ]
        if not threats:
            self._show_status("Нет угроз для удаления")
            return

        reply = QMessageBox.question(
            self, "⚠ Подтверждение удаления",
            f"Удалить {len(threats)} подозрительных файлов?\n\n"
            f"Это действие необратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        count = 0
        for r in threats:
            if FileRemediator.delete(r.path):
                count += 1
        self._show_status(f"🗑 Удалено: {count}/{len(threats)}")

    # ── Статус ─────────────────────────────────────────────────────────────

    def _show_status(self, message: str):
        self._status.showMessage(message, 5000)

    # ── Закрытие ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._scanner_worker and self._scanner_worker.isRunning():
            self._scanner_worker.stop()
            self._scanner_worker.wait(3000)
        super().closeEvent(event)