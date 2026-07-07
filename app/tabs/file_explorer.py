"""
Встроенный файловый проводник с контекстным меню.
Замена стандартному проводнику в WinPE/WinRE.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QDir, QFileInfo, QModelIndex,
    QSortFilterProxyModel, pyqtSignal, QThread, QObject, QPoint,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QHeaderView, QLineEdit, QComboBox, QMenu,
    QInputDialog, QMessageBox, QSplitter,
    QTextEdit, QFrame, QFileDialog, QApplication,
)
from PyQt6.QtGui import QAction, QKeySequence, QFont, QFontMetrics, QFileSystemModel

from app.utils.theme import ColorPalette


class FileExplorerTab(QWidget):
    """Вкладка файлового проводника."""

    status_message = pyqtSignal(str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._current_path = ""
        self._model: QFileSystemModel | None = None
        self._setup_ui()

    def _setup_ui(self):
        p = self._palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Заголовок ──────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("📁 Файловый проводник")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        header.addWidget(title)
        header.addStretch()

        # Кнопка «Открыть в стандартном проводнике»
        open_ext = QPushButton("📂 Открыть в Проводнике")
        open_ext.setProperty("small", True)
        open_ext.clicked.connect(self._open_in_explorer_external)
        header.addWidget(open_ext)
        layout.addLayout(header)

        # ── Строка навигации ───────────────────────────────────────────
        nav = QHBoxLayout()
        nav.setSpacing(6)

        self._back_btn = QPushButton("⬅")
        self._back_btn.setProperty("small", True)
        self._back_btn.setFixedWidth(36)
        self._back_btn.clicked.connect(self._go_up)
        nav.addWidget(self._back_btn)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Введите путь...")
        self._path_edit.returnPressed.connect(self._navigate_to_path)
        nav.addWidget(self._path_edit, 1)

        self._go_btn = QPushButton("Перейти")
        self._go_btn.setProperty("small", True)
        self._go_btn.clicked.connect(self._navigate_to_path)
        nav.addWidget(self._go_btn)

        # Быстрые переходы
        self._quick_combo = QComboBox()
        self._quick_combo.setMinimumWidth(150)
        self._quick_combo.addItem("Быстрый переход...", "")
        self._quick_combo.insertSeparator(1)
        drives = self._get_drives()
        for label, path in drives:
            self._quick_combo.addItem(f"{label} ({path})", path)
        self._quick_combo.insertSeparator(len(drives) + 2)
        special = [
            ("Рабочий стол", os.path.expanduser("~\\Desktop")),
            ("Документы", os.path.expanduser("~\\Documents")),
            ("Загрузки", os.path.expanduser("~\\Downloads")),
            ("System32", os.environ.get("SystemRoot", "C:\\Windows") + "\\System32"),
            ("Program Files", os.environ.get("ProgramFiles", "C:\\Program Files")),
        ]
        for label, path in special:
            if os.path.isdir(path):
                self._quick_combo.addItem(f"📌 {label}", path)
        self._quick_combo.currentIndexChanged.connect(self._quick_navigate)
        nav.addWidget(self._quick_combo)

        layout.addLayout(nav)

        # ── Сплиттер: дерево + панель предпросмотра ────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Модель файловой системы
        self._model = QFileSystemModel()
        self._model.setRootPath("")
        self._model.setFilter(
            QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot |
            QDir.Filter.Hidden | QDir.Filter.System
        )
        self._model.setNameFilters(["*"])
        self._model.setNameFilterDisables(False)

        # Прокси для сортировки
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # Дерево
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setSortingEnabled(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Настройка колонок
        header_view = self._tree.header()
        header_view.setStretchLastSection(True)
        self._tree.setColumnWidth(0, 300)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 160)
        self._tree.setColumnWidth(3, 120)

        self._splitter.addWidget(self._tree)

        # ── Панель предпросмотра ───────────────────────────────────────
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)

        preview_label = QLabel("📄 Предпросмотр")
        preview_label.setStyleSheet(f"font-weight: bold; color: {p.text_secondary};")
        preview_layout.addWidget(preview_label)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setFont(QFont("Consolas", 10))
        self._preview_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {p.terminal_bg};
                color: {p.terminal_text};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        self._preview_text.setPlaceholderText("Выберите файл для предпросмотра...")
        preview_layout.addWidget(self._preview_text)

        # Информация о файле
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 11px; padding: 4px;")
        preview_layout.addWidget(self._info_label)

        self._splitter.addWidget(preview_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter, 1)

        # ── Статус-бар ─────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Инициализация ──────────────────────────────────────────────
        self._set_root_path("C:\\")
        self._tree.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ── Навигация ──────────────────────────────────────────────────────────

    def _set_root_path(self, path: str):
        """Устанавливает корневой путь дерева."""
        if not os.path.isdir(path):
            return
        self._current_path = path
        self._path_edit.setText(path)

        src_index = self._model.index(path)
        proxy_index = self._proxy.mapFromSource(src_index)
        self._tree.setRootIndex(proxy_index)
        self._status_label.setText(f"📂 {path}")
        self.status_message.emit(f"Открыто: {path}")

    def _navigate_to_path(self):
        """Переход по пути из строки ввода."""
        path = self._path_edit.text().strip()
        if not path:
            return
        path = os.path.abspath(path)
        if os.path.isdir(path):
            self._set_root_path(path)
        elif os.path.isfile(path):
            parent = os.path.dirname(path)
            self._set_root_path(parent)
            # Выделить файл
            src = self._model.index(path)
            proxy = self._proxy.mapFromSource(src)
            self._tree.scrollTo(proxy)
            self._tree.setCurrentIndex(proxy)
        else:
            QMessageBox.warning(self, "Ошибка", f"Путь не существует:\n{path}")

    def _go_up(self):
        """Подняться на уровень выше."""
        parent = os.path.dirname(self._current_path)
        if os.path.isdir(parent):
            self._set_root_path(parent)

    def _quick_navigate(self, idx: int):
        """Быстрый переход из выпадающего списка."""
        path = self._quick_combo.currentData()
        if path and os.path.isdir(path):
            self._set_root_path(path)

    def _on_double_click(self, index: QModelIndex):
        """Обработка двойного клика: вход в папку или открытие файла."""
        src = self._proxy.mapToSource(index)
        info: QFileInfo = self._model.fileInfo(src)
        if info.isDir():
            self._set_root_path(info.absoluteFilePath())
        else:
            self._open_file(info.absoluteFilePath())

    # ── Выделение и предпросмотр ───────────────────────────────────────────

    def _on_selection_changed(self):
        """Обновляет панель предпросмотра при смене выделения."""
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            return
        src = self._proxy.mapToSource(indexes[0])
        info = self._model.fileInfo(src)
        filepath = info.absoluteFilePath()

        # Информация
        try:
            stat = os.stat(filepath)
            size = self._format_size(stat.st_size) if not info.isDir() else "Папка"
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
            self._info_label.setText(
                f"📄 {info.fileName()}\n"
                f"Размер: {size}\n"
                f"Изменён: {mtime}\n"
                f"Путь: {filepath}"
            )
        except OSError:
            self._info_label.setText(f"📄 {info.fileName()}\n(недоступно)")

        # Предпросмотр текстовых файлов
        if info.isFile() and info.size() < 512 * 1024:  # < 512 КБ
            ext = info.suffix().lower()
            text_exts = {
                ".txt", ".log", ".ini", ".cfg", ".conf", ".xml", ".json",
                ".csv", ".py", ".js", ".html", ".css", ".bat", ".cmd",
                ".ps1", ".reg", ".inf", ".yaml", ".yml", ".md", ".rst",
                ".sql", ".php", ".c", ".cpp", ".h", ".java", ".cs",
            }
            if ext in text_exts:
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(4096)  # первые 4 КБ
                    self._preview_text.setPlainText(content)
                except Exception:
                    self._preview_text.setPlainText("(не удалось прочитать файл)")
            else:
                self._preview_text.setPlainText(f"(бинарный файл: {ext})")
        else:
            self._preview_text.clear()

    # ── Контекстное меню ───────────────────────────────────────────────────

    def _show_context_menu(self, pos: QPoint):
        """Показывает контекстное меню для выделенных элементов."""
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            return

        paths = []
        for idx in indexes:
            src = self._proxy.mapToSource(idx)
            info = self._model.fileInfo(src)
            paths.append(info.absoluteFilePath())

        is_single = len(paths) == 1
        is_dir = os.path.isdir(paths[0]) if is_single else False

        menu = QMenu(self)

        # Открыть
        act_open = menu.addAction("📂 Открыть")
        act_open.triggered.connect(lambda: self._action_open(paths[0]) if is_single else None)
        act_open.setEnabled(is_single)

        # Открыть в стандартном проводнике
        act_explorer = menu.addAction("📁 Открыть в Проводнике")
        act_explorer.triggered.connect(lambda: self._open_in_explorer(paths[0]) if is_single else None)
        act_explorer.setEnabled(is_single and is_dir)

        menu.addSeparator()

        # Копировать
        act_copy = menu.addAction("📋 Копировать")
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(lambda: self._copy_paths(paths))

        # Копировать путь
        act_copy_path = menu.addAction("📎 Копировать путь")
        act_copy_path.triggered.connect(lambda: self._copy_paths(paths))

        menu.addSeparator()

        # Удалить
        act_delete = menu.addAction("🗑 Удалить")
        act_delete.setShortcut("Del")
        act_delete.setEnabled(all(os.access(p, os.W_OK) for p in paths))
        act_delete.triggered.connect(lambda: self._action_delete(paths))

        # Переименовать
        act_rename = menu.addAction("✏ Переименовать")
        act_rename.setShortcut("F2")
        act_rename.setEnabled(is_single and os.access(paths[0], os.W_OK))
        act_rename.triggered.connect(lambda: self._action_rename(paths[0]) if is_single else None)

        # Новая папка
        act_mkdir = menu.addAction("📁 Создать папку")
        act_mkdir.setEnabled(is_single and is_dir and os.access(paths[0], os.W_OK))
        act_mkdir.triggered.connect(lambda: self._action_mkdir(paths[0] if is_single else self._current_path))

        menu.addSeparator()

        # Свойства
        act_props = menu.addAction("ℹ Свойства")
        act_props.triggered.connect(lambda: self._action_properties(paths[0]) if is_single else None)
        act_props.setEnabled(is_single)

        # Запуск от администратора
        act_runas = menu.addAction("🛡 Запустить от администратора")
        act_runas.setEnabled(is_single and not is_dir)
        act_runas.triggered.connect(lambda: self._action_runas(paths[0]) if is_single else None)

        # Сканировать на вирусы
        act_scan = menu.addAction("🛡 Сканировать на вирусы")
        act_scan.triggered.connect(lambda: self._request_scan(paths))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── Действия ───────────────────────────────────────────────────────────

    def _action_open(self, path: str):
        if os.path.isdir(path):
            self._set_root_path(path)
        else:
            self._open_file(path)

    def _open_file(self, path: str):
        """Открывает файл в ассоциированной программе."""
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл:\n{e}")

    def _open_in_explorer(self, path: str):
        """Открывает папку в стандартном проводнике Windows."""
        try:
            subprocess.Popen(["explorer.exe", path])
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть проводник:\n{e}")

    def _open_in_explorer_external(self):
        """Открывает текущую папку в проводнике."""
        self._open_in_explorer(self._current_path)

    def _copy_paths(self, paths: list[str]):
        QApplication.clipboard().setText("\n".join(paths))
        self.status_message.emit(f"Скопировано: {len(paths)} элементов")

    def _action_delete(self, paths: list[str]):
        msg = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {len(paths)} элемент(ов)?\n\n"
            + "\n".join(f"  • {os.path.basename(p)}" for p in paths[:10])
            + ("\n  ..." if len(paths) > 10 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if msg != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
                deleted += 1
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить:\n{path}\n{e}")

        self.status_message.emit(f"Удалено: {deleted}/{len(paths)} элементов")

    def _action_rename(self, path: str):
        name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(
            self, "Переименовать", "Новое имя:", text=name,
        )
        if ok and new_name and new_name != name:
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
                self.status_message.emit(f"Переименовано: {name} → {new_name}")
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать:\n{e}")

    def _action_mkdir(self, parent_path: str):
        name, ok = QInputDialog.getText(
            self, "Новая папка", "Имя папки:", text="Новая папка",
        )
        if ok and name:
            new_path = os.path.join(parent_path, name)
            try:
                os.makedirs(new_path, exist_ok=False)
                self.status_message.emit(f"Создана папка: {name}")
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать папку:\n{e}")

    def _action_properties(self, path: str):
        """Показывает свойства файла/папки."""
        try:
            stat = os.stat(path)
            is_dir = os.path.isdir(path)
            size = self._format_size(stat.st_size) if not is_dir else "—"
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
            ctime = datetime.fromtimestamp(stat.st_ctime).strftime("%d.%m.%Y %H:%M:%S")

            QMessageBox.information(
                self, "Свойства",
                f"Имя: {os.path.basename(path)}\n"
                f"Тип: {'Папка' if is_dir else 'Файл'}\n"
                f"Путь: {os.path.dirname(path)}\n"
                f"Размер: {size}\n"
                f"Создан: {ctime}\n"
                f"Изменён: {mtime}\n"
                f"Атрибуты: {stat.st_file_attributes if hasattr(stat, 'st_file_attributes') else '—'}"
            )
        except OSError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _action_runas(self, path: str):
        """Запускает файл от имени администратора."""
        try:
            ret = subprocess.Popen(
                ["runas", "/user:Administrator", path],
                shell=True,
            )
            if ret.returncode:
                raise RuntimeError(f"runas exited with {ret.returncode}")
        except Exception as e:
            # Fallback: пытаемся через ShellExecute с runas
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", path, None, None, 1
                )
            except Exception as e2:
                QMessageBox.warning(
                    self, "Ошибка",
                    f"Не удалось запустить от администратора:\n{e}\n{e2}"
                )

    def _request_scan(self, paths: list[str]):
        """Сигнализирует главному окну о запросе сканирования."""
        self.status_message.emit(f"Запрос сканирования: {len(paths)} файл(ов)")

    # ── Утилиты ────────────────────────────────────────────────────────────

    @staticmethod
    def _get_drives() -> list[tuple[str, str]]:
        """Возвращает список доступных дисков."""
        drives = []
        import string
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                try:
                    import ctypes
                    buf = ctypes.create_unicode_buffer(128)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        path, buf, 128, None, None, None, None, 0
                    )
                    label = buf.value or "Локальный диск"
                except Exception:
                    label = "Локальный диск"
                drives.append((label, path))
        return drives

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
            if abs(size) < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ПБ"