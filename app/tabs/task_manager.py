"""
Встроенный диспетчер задач с контекстным меню.
Замена стандартному Task Manager в WinPE/WinRE.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from enum import Enum
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSortFilterProxyModel,
    QAbstractTableModel, QModelIndex, QVariant,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QHeaderView, QLineEdit, QMenu, QMessageBox,
    QSplitter, QTextEdit, QGroupBox, QComboBox, QFrame,
    QAbstractItemView, QCheckBox,
)
from PyQt6.QtGui import QAction, QFont

from app.utils.theme import ColorPalette

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


# Сигналы для потоков
class SortColumn(Enum):
    PID = 0
    NAME = 1
    CPU = 2
    MEMORY = 3
    STATUS = 4
    USER = 6


class ProcessTableModel(QAbstractTableModel):
    """Модель таблицы процессов."""

    COLUMNS = ["PID", "Имя", "CPU %", "Память", "Статус", "Путь", "Пользователь"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processes: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._processes)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        row = index.row()
        col = index.column()
        proc = self._processes[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return str(proc.get(self._col_key(col), ""))
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 2, 3):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.UserRole:
            return proc.get("pid", 0)
        return QVariant()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return QVariant()

    def _col_key(self, col: int) -> str:
        return ["pid", "name", "cpu_percent", "memory_mb", "status", "exe", "username"][col]

    def update_data(self, processes: list[dict]):
        self.beginResetModel()
        self._processes = processes
        self.endResetModel()

    def get_process(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._processes):
            return self._processes[row]
        return None


class ProcessRefreshWorker(QThread):
    """Фоновый поток обновления списка процессов."""
    data_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            processes = []
            if _HAS_PSUTIL:
                for proc in psutil.process_iter([
                    "pid", "name", "cpu_percent", "memory_info",
                    "status", "exe", "username",
                ]):
                    try:
                        info = proc.info
                        mem_mb = 0.0
                        if info.get("memory_info"):
                            mem_mb = info["memory_info"].rss / (1024 * 1024)
                        processes.append({
                            "pid": info["pid"],
                            "name": info["name"] or "",
                            "cpu_percent": f"{info.get('cpu_percent', 0.0):.1f}",
                            "memory_mb": f"{mem_mb:.1f}",
                            "status": info.get("status", ""),
                            "exe": info.get("exe") or "",
                            "username": (info.get("username") or "").split("\\")[-1],
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                # Сортируем по CPU
                processes.sort(key=lambda p: float(p["cpu_percent"]), reverse=True)

            self.data_ready.emit(processes)
            time.sleep(1.5)  # Интервал обновления


class TaskManagerTab(QWidget):
    """Вкладка диспетчера задач."""

    status_message = pyqtSignal(str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._worker: Optional[ProcessRefreshWorker] = None
        self._auto_refresh = True
        self._setup_ui()
        self._start_refresh()

    def _setup_ui(self):
        p = self._palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Заголовок ──────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("📊 Диспетчер задач")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        header.addWidget(title)
        header.addStretch()

        # Информация о системе
        self._sys_info_label = QLabel("Загрузка...")
        self._sys_info_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        header.addWidget(self._sys_info_label)
        layout.addLayout(header)

        # ── Панель инструментов ────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 Фильтр по имени/PID...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_edit, 1)

        self._auto_refresh_cb = QCheckBox("Автообновление")
        self._auto_refresh_cb.setChecked(True)
        self._auto_refresh_cb.toggled.connect(self._toggle_auto_refresh)
        toolbar.addWidget(self._auto_refresh_cb)

        self._refresh_btn = QPushButton("🔄 Обновить")
        self._refresh_btn.setProperty("small", True)
        self._refresh_btn.clicked.connect(self._manual_refresh)
        toolbar.addWidget(self._refresh_btn)

        self._end_task_btn = QPushButton("⏹ Завершить")
        self._end_task_btn.setProperty("small", True)
        self._end_task_btn.setProperty("danger", True)
        self._end_task_btn.clicked.connect(self._end_selected_task)
        toolbar.addWidget(self._end_task_btn)

        layout.addLayout(toolbar)

        # ── Сплиттер: таблица + детали ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Модель и таблица
        self._model = ProcessTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setSortingEnabled(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.doubleClicked.connect(self._on_double_click_process)

        # Колонки
        hdr = self._tree.header()
        hdr.setStretchLastSection(True)
        self._tree.setColumnWidth(0, 70)   # PID
        self._tree.setColumnWidth(1, 180)  # Имя
        self._tree.setColumnWidth(2, 70)   # CPU
        self._tree.setColumnWidth(3, 90)   # Память
        self._tree.setColumnWidth(4, 90)   # Статус
        self._tree.setColumnWidth(5, 250)  # Путь
        hdr.setSortIndicator(2, Qt.SortOrder.DescendingOrder)  # сортировка по CPU

        splitter.addWidget(self._tree)

        # ── Панель деталей ─────────────────────────────────────────────
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        detail_title = QLabel("🔍 Детали процесса")
        detail_title.setStyleSheet(f"font-weight: bold; color: {p.text_secondary};")
        detail_layout.addWidget(detail_title)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setFont(QFont("Consolas", 10))
        self._detail_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {p.terminal_bg};
                color: {p.terminal_text};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        self._detail_text.setPlaceholderText("Выберите процесс для просмотра деталей...")
        detail_layout.addWidget(self._detail_text, 1)

        # Кнопки действий в деталях
        det_btn_row = QHBoxLayout()
        self._detail_end_btn = QPushButton("⏹ Завершить процесс")
        self._detail_end_btn.setProperty("danger", True)
        self._detail_end_btn.clicked.connect(self._end_selected_task)

        self._detail_tree_btn = QPushButton("🌳 Дерево процессов")
        self._detail_tree_btn.setProperty("small", True)
        self._detail_tree_btn.clicked.connect(self._kill_process_tree)

        self._detail_open_btn = QPushButton("📂 Открыть путь")
        self._detail_open_btn.setProperty("small", True)
        self._detail_open_btn.clicked.connect(self._open_process_path)

        det_btn_row.addWidget(self._detail_end_btn)
        det_btn_row.addWidget(self._detail_tree_btn)
        det_btn_row.addWidget(self._detail_open_btn)
        det_btn_row.addStretch()
        detail_layout.addLayout(det_btn_row)

        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # ── Статус-бар ─────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Подключаем сигналы ─────────────────────────────────────────
        self._tree.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ── Обновление данных ──────────────────────────────────────────────────

    def _start_refresh(self):
        """Запускает фоновый поток обновления."""
        if not _HAS_PSUTIL:
            self._status_label.setText("⚠ psutil не установлен. Диспетчер задач недоступен.")
            self.status_message.emit("psutil не установлен")
            return
        self._worker = ProcessRefreshWorker()
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.start()

    def _stop_refresh(self):
        """Останавливает фоновый поток."""
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)

    def _toggle_auto_refresh(self, enabled: bool):
        self._auto_refresh = enabled
        if enabled and not self._worker:
            self._start_refresh()
        elif not enabled:
            self._stop_refresh()

    def _manual_refresh(self):
        if self._worker is None:
            self._start_refresh()
            return
        if not self._worker.isRunning():
            self._worker.start()

    def _on_data_ready(self, processes: list[dict]):
        self._model.update_data(processes)
        self._status_label.setText(f"Процессов: {len(processes)}")
        self._update_system_info(processes)

    def _update_system_info(self, processes: list[dict]):
        """Обновляет сводку системы."""
        total_cpu = sum(float(p.get("cpu_percent", 0)) for p in processes)
        total_mem = sum(float(p.get("memory_mb", 0)) for p in processes)
        try:
            mem_total = psutil.virtual_memory().total / (1024 ** 3) if _HAS_PSUTIL else 0
            mem_text = f"{total_mem:.0f} МБ / {mem_total:.1f} ГБ"
        except Exception:
            mem_text = f"{total_mem:.0f} МБ"
        self._sys_info_label.setText(
            f"CPU: {total_cpu:.1f}% | Память: {mem_text} | "
            f"Процессов: {len(processes)}"
        )

    def _apply_filter(self):
        text = self._search_edit.text().strip()
        self._proxy.setFilterFixedString(text)

    # ── Выделение и детали ─────────────────────────────────────────────────

    def _on_selection_changed(self):
        """Обновляет панель деталей при выборе процесса."""
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            self._detail_text.clear()
            return

        src_idx = self._proxy.mapToSource(indexes[0])
        proc = self._model.get_process(src_idx.row())
        if not proc:
            return

        detail = (
            f"PID:           {proc.get('pid', '')}\n"
            f"Имя:           {proc.get('name', '')}\n"
            f"CPU:           {proc.get('cpu_percent', '')}%\n"
            f"Память:        {proc.get('memory_mb', '')} МБ\n"
            f"Статус:        {proc.get('status', '')}\n"
            f"Пользователь:  {proc.get('username', '')}\n"
            f"Путь:          {proc.get('exe', '')}\n"
        )
        self._detail_text.setPlainText(detail)

    def _on_double_click_process(self, index: QModelIndex):
        """Двойной клик — показать детали."""
        self._on_selection_changed()

    # ── Контекстное меню ───────────────────────────────────────────────────

    def _show_context_menu(self, pos):
        indexes = self._tree.selectionModel().selectedRows()
        if not indexes:
            return

        pids = []
        for idx in indexes:
            src = self._proxy.mapToSource(idx)
            proc = self._model.get_process(src.row())
            if proc:
                pids.append(proc["pid"])

        if not pids:
            return

        menu = QMenu(self)

        act_end = menu.addAction("⏹ Завершить процесс")
        act_end.triggered.connect(lambda: self._kill_processes(pids))

        act_tree = menu.addAction("🌳 Завершить дерево процессов")
        act_tree.triggered.connect(lambda: self._kill_process_tree_pids(pids))

        menu.addSeparator()

        act_suspend = menu.addAction("⏸ Приостановить")
        act_suspend.triggered.connect(lambda: self._suspend_processes(pids))

        act_resume = menu.addAction("▶ Возобновить")
        act_resume.triggered.connect(lambda: self._resume_processes(pids))

        menu.addSeparator()

        act_open = menu.addAction("📂 Открыть расположение")
        act_open.triggered.connect(lambda: self._open_process_location(pids[0]))

        act_props = menu.addAction("ℹ Свойства файла")
        act_props.triggered.connect(lambda: self._show_file_properties(pids[0]))

        menu.addSeparator()

        act_priority = menu.addAction("⚡ Приоритет → Высокий")
        act_priority.triggered.connect(lambda: self._set_priority(pids[0], "high"))

        act_priority_norm = menu.addAction("⚡ Приоритет → Нормальный")
        act_priority_norm.triggered.connect(lambda: self._set_priority(pids[0], "normal"))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── Действия над процессами ────────────────────────────────────────────

    def _get_selected_pids(self) -> list[int]:
        indexes = self._tree.selectionModel().selectedRows()
        pids = []
        for idx in indexes:
            src = self._proxy.mapToSource(idx)
            proc = self._model.get_process(src.row())
            if proc:
                pids.append(proc["pid"])
        return pids

    def _end_selected_task(self):
        pids = self._get_selected_pids()
        if not pids:
            return
        self._kill_processes(pids)

    def _kill_processes(self, pids: list[int]):
        names = []
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                names.append(proc.name())
            except Exception:
                names.append(f"PID {pid}")

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Завершить процессы?\n\n" + "\n".join(f"  • {n}" for n in names[:10]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        killed = 0
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=3)
                killed += 1
            except psutil.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                    killed += 1
                except Exception:
                    pass
            except Exception:
                pass

        self.status_message.emit(f"Завершено процессов: {killed}/{len(pids)}")

    def _kill_process_tree(self):
        pids = self._get_selected_pids()
        self._kill_process_tree_pids(pids)

    def _kill_process_tree_pids(self, pids: list[int]):
        killed = 0
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                children = proc.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                proc.terminate()
                gone, alive = psutil.wait_procs([proc] + children, timeout=5)
                for p in alive:
                    try:
                        p.kill()
                    except Exception:
                        pass
                killed += 1
            except Exception:
                pass
        self.status_message.emit(f"Завершено деревьев: {killed}/{len(pids)}")

    def _suspend_processes(self, pids: list[int]):
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.suspend()
            except Exception:
                pass
        self.status_message.emit(f"Приостановлено: {len(pids)} процессов")

    def _resume_processes(self, pids: list[int]):
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.resume()
            except Exception:
                pass
        self.status_message.emit(f"Возобновлено: {len(pids)} процессов")

    def _set_priority(self, pid: int, level: str):
        import psutil as pu
        try:
            proc = psutil.Process(pid)
            if level == "high":
                proc.nice(pu.HIGH_PRIORITY_CLASS)
            elif level == "normal":
                proc.nice(pu.NORMAL_PRIORITY_CLASS)
            self.status_message.emit(f"Приоритет PID {pid}: {level}")
        except Exception as e:
            self.status_message.emit(f"Ошибка приоритета: {e}")

    def _open_process_path(self):
        pids = self._get_selected_pids()
        if pids:
            self._open_process_location(pids[0])

    def _open_process_location(self, pid: int):
        """Открывает папку с исполняемым файлом процесса."""
        try:
            proc = psutil.Process(pid)
            exe = proc.exe()
            if exe:
                import subprocess
                subprocess.Popen(["explorer.exe", "/select,", exe])
        except Exception as e:
            self.status_message.emit(f"Ошибка: {e}")

    def _show_file_properties(self, pid: int):
        """Показывает свойства файла процесса."""
        try:
            proc = psutil.Process(pid)
            exe = proc.exe()
            if exe:
                import subprocess
                subprocess.Popen(["explorer.exe", "shell:::{328B0346-7EAF-4BBF-A479-7CB88A095F5B}"],
                                 shell=True)
        except Exception:
            pass

    # ── Очистка ────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop_refresh()
        super().closeEvent(event)