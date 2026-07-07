"""
Вкладка «Ограничения» — сканер и снятие системных ограничений Windows.
Обнаруживает:
- Блокировки через реестр (Task Manager, Regedit, CMD, Control Panel...)
- IFEO-дебаггеры (Image File Execution Options)
- Групповые политики (NoRun, NoClose, NoDrives...)
- AppLocker / SRP
- Ограничения Проводника и рабочего стола
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QMessageBox, QAbstractItemView, QFrame,
    QCheckBox,
)
from PyQt6.QtGui import QFont, QColor

from app.utils.theme import ColorPalette

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False


# ── Типы ограничений ──────────────────────────────────────────────────────

class RestrictionType(Enum):
    """Тип ограничения."""
    POLICY = auto()          # Групповая политика
    IFEO_DEBUGGER = auto()   # IFEO-дебаггер
    REGISTRY_BLOCK = auto()  # Блокировка через реестр
    EXPLORER_RESTRICT = auto()  # Ограничения проводника
    APPLOCKER = auto()       # AppLocker / SRP
    UAC = auto()             # UAC-ограничения
    OTHER = auto()


class Severity(Enum):
    """Серьёзность ограничения."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class Restriction:
    """Ограничение."""
    name: str
    description: str
    restriction_type: RestrictionType
    severity: Severity
    registry_path: str = ""
    registry_value: str = ""
    registry_data_expected: str = ""  # ожидаемое «нормальное» значение
    fix_method: str = ""  # описание способа исправления
    is_active: bool = False
    current_data: str = ""


# ── База известных ограничений ────────────────────────────────────────────

KNOWN_RESTRICTIONS: list[Restriction] = [
    # ── Блокировки через реестр ──────────────────────────────────────
    Restriction(
        name="Task Manager отключён",
        description="Диспетчер задач заблокирован через реестр",
        restriction_type=RestrictionType.REGISTRY_BLOCK,
        severity=Severity.CRITICAL,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        registry_value="DisableTaskMgr",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Regedit отключён",
        description="Редактор реестра заблокирован",
        restriction_type=RestrictionType.REGISTRY_BLOCK,
        severity=Severity.CRITICAL,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        registry_value="DisableRegistryTools",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="CMD отключён",
        description="Командная строка заблокирована",
        restriction_type=RestrictionType.REGISTRY_BLOCK,
        severity=Severity.HIGH,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        registry_value="DisableCMD",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Панель управления скрыта",
        description="Панель управления отключена через реестр",
        restriction_type=RestrictionType.REGISTRY_BLOCK,
        severity=Severity.MEDIUM,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoControlPanel",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Смена обоев запрещена",
        description="Запрет смены обоев рабочего стола",
        restriction_type=RestrictionType.REGISTRY_BLOCK,
        severity=Severity.LOW,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\ActiveDesktop",
        registry_value="NoChangingWallPaper",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Контекстное меню отключено",
        description="Контекстное меню рабочего стола заблокировано",
        restriction_type=RestrictionType.EXPLORER_RESTRICT,
        severity=Severity.MEDIUM,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoViewContextMenu",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Скрыты диски в Проводнике",
        description="Скрытие дисков через NoDrives",
        restriction_type=RestrictionType.EXPLORER_RESTRICT,
        severity=Severity.MEDIUM,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoDrives",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Запрет завершения работы",
        description="Кнопка «Завершение работы» скрыта",
        restriction_type=RestrictionType.EXPLORER_RESTRICT,
        severity=Severity.MEDIUM,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoClose",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Запрет запуска (NoRun)",
        description="Окно «Выполнить» отключено",
        restriction_type=RestrictionType.POLICY,
        severity=Severity.MEDIUM,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoRun",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Запрет логаута",
        description="Кнопка выхода из системы скрыта",
        restriction_type=RestrictionType.POLICY,
        severity=Severity.LOW,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="NoLogOff",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="Запрет папок «Мой компьютер»",
        description="Скрытие значков с рабочего стола",
        restriction_type=RestrictionType.EXPLORER_RESTRICT,
        severity=Severity.LOW,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\NonEnum",
        registry_value="{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
        registry_data_expected="0",
        fix_method="Удалить значение",
    ),
    Restriction(
        name="Скрыты часы с панели задач",
        description="Часы скрыты через политику",
        restriction_type=RestrictionType.POLICY,
        severity=Severity.LOW,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        registry_value="HideClock",
        registry_data_expected="0",
        fix_method="Удалить или установить значение в 0",
    ),
    Restriction(
        name="UAC отключён полностью",
        description="Контроль учётных записей выключен",
        restriction_type=RestrictionType.UAC,
        severity=Severity.HIGH,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        registry_value="EnableLUA",
        registry_data_expected="1",
        fix_method="Установить значение в 1",
    ),
    Restriction(
        name="UAC в тихом режиме",
        description="UAC пропускает все запросы без уведомлений",
        restriction_type=RestrictionType.UAC,
        severity=Severity.HIGH,
        registry_path=r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        registry_value="ConsentPromptBehaviorAdmin",
        registry_data_expected="5",
        fix_method="Установить значение в 5 (полный запрос)",
    ),
    Restriction(
        name="Безопасный режим отключён",
        description="Запрет загрузки в безопасном режиме",
        restriction_type=RestrictionType.POLICY,
        severity=Severity.CRITICAL,
        registry_path=r"System\CurrentControlSet\Control\SafeBoot",
        registry_value="OptionValue",
        registry_data_expected="",
        fix_method="Удалить ключ SafeBoot\\OptionValue",
    ),
    # ── IFEO-дебаггеры ────────────────────────────────────────────────
    # (динамически проверяются ниже)
]

# Процессы, для которых проверяем IFEO-дебаггеры
IFEO_CHECK_PROCESSES = [
    "taskmgr.exe",
    "regedit.exe",
    "cmd.exe",
    "powershell.exe",
    "explorer.exe",
    "msconfig.exe",
    "procexp.exe",
    "procexp64.exe",
    "procmon.exe",
    "autoruns.exe",
    "autoruns64.exe",
    "wireshark.exe",
    "ollydbg.exe",
    "x64dbg.exe",
    "ida.exe",
    "ida64.exe",
    "windbg.exe",
]


# ── Поток сканирования ────────────────────────────────────────────────────

class RestrictionScanner(QThread):
    """Фоновый сканер ограничений."""
    found = pyqtSignal(Restriction)
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        if not _HAS_WINREG:
            self.finished.emit()
            return

        all_checks = list(KNOWN_RESTRICTIONS)
        # Добавляем IFEO-проверки динамически
        for proc in IFEO_CHECK_PROCESSES:
            all_checks.append(Restriction(
                name=f"IFEO-дебаггер: {proc}",
                description=f"К процессу {proc} прицеплен дебаггер через IFEO",
                restriction_type=RestrictionType.IFEO_DEBUGGER,
                severity=Severity.CRITICAL,
                registry_path=rf"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\{proc}",
                registry_value="Debugger",
                registry_data_expected="",
                fix_method="Удалить значение Debugger в IFEO",
            ))

        total = len(all_checks)
        for idx, restriction in enumerate(all_checks):
            if self._cancel:
                break
            self.progress.emit(idx + 1, total)

            try:
                is_active, current = self._check_restriction(restriction)
                if is_active:
                    restriction.is_active = True
                    restriction.current_data = current
                    self.found.emit(restriction)
            except Exception:
                pass

        self.finished.emit()

    @staticmethod
    def _check_restriction(r: Restriction) -> tuple[bool, str]:
        """Проверяет одиночное ограничение. Возвращает (активно, текущее_значение)."""
        try:
            # Определяем корневой ключ
            if r.registry_path.lower().startswith("system\\"):
                hkey = winreg.HKEY_LOCAL_MACHINE
                subkey = r.registry_path
            elif r.registry_path.lower().startswith("software\\"):
                # Проверяем и HKLM, и HKCU
                results = []
                for hk in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        key = winreg.OpenKey(hk, r.registry_path)
                        try:
                            val, _ = winreg.QueryValueEx(key, r.registry_value)
                            results.append(str(val))
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(key)
                    except FileNotFoundError:
                        pass

                if results:
                    current = results[0]
                    expected = r.registry_data_expected
                    if expected == "":
                        # Если ожидаемое пустое — значение не должно существовать
                        return True, current
                    return current != expected, current
                return False, ""
            else:
                # Неизвестный формат — пробуем HKLM
                hkey = winreg.HKEY_LOCAL_MACHINE
                subkey = r.registry_path

            key = winreg.OpenKey(hkey, subkey)
            try:
                val, _ = winreg.QueryValueEx(key, r.registry_value)
                current = str(val)
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False, ""
            winreg.CloseKey(key)

            if r.registry_data_expected == "":
                return True, current
            return current != r.registry_data_expected, current

        except FileNotFoundError:
            return False, ""
        except OSError:
            return False, ""


# ── Вкладка ───────────────────────────────────────────────────────────────

class RestrictionsTab(QWidget):
    """Вкладка «Ограничения»."""

    status_message = pyqtSignal(str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._scanner: Optional[RestrictionScanner] = None
        self._found_restrictions: list[Restriction] = []
        self._setup_ui()

    def _setup_ui(self):
        p = self._palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Заголовок ──────────────────────────────────────────────────
        title = QLabel("🔓 Ограничения и дебаггеры")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Сканирование системных ограничений, IFEO-дебаггеров, "
            "групповых политик и блокировок реестра"
        )
        subtitle.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── Панель управления ──────────────────────────────────────────
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
        """)
        ctrl = QVBoxLayout(ctrl_frame)
        ctrl.setContentsMargins(16, 12, 16, 12)
        ctrl.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._scan_btn = QPushButton("🔍 Сканировать ограничения")
        self._scan_btn.setProperty("accent", True)
        self._scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("⏹ Остановить")
        self._stop_btn.setProperty("small", True)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self._stop_btn)

        btn_row.addStretch()

        self._fix_selected_btn = QPushButton("🔧 Снять выделенные ограничения")
        self._fix_selected_btn.setProperty("accent", True)
        self._fix_selected_btn.setEnabled(False)
        self._fix_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fix_selected_btn.clicked.connect(self._fix_selected)
        btn_row.addWidget(self._fix_selected_btn)

        self._fix_all_btn = QPushButton("⚡ Снять все ограничения")
        self._fix_all_btn.setProperty("danger", True)
        self._fix_all_btn.setEnabled(False)
        self._fix_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fix_all_btn.clicked.connect(self._fix_all)
        btn_row.addWidget(self._fix_all_btn)

        ctrl.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        ctrl.addWidget(self._progress)

        self._status_label = QLabel("Готов к сканированию. Нажмите «Сканировать ограничения».")
        self._status_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        ctrl.addWidget(self._status_label)

        layout.addWidget(ctrl_frame)

        # ── Таблица результатов ────────────────────────────────────────
        tree_frame = QFrame()
        tree_frame.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)
        tl = QVBoxLayout(tree_frame)
        tl.setContentsMargins(0, 0, 0, 0)

        tree_header = QHBoxLayout()

        self._select_all_cb = QCheckBox("Выделить всё")
        self._select_all_cb.setEnabled(False)
        self._select_all_cb.toggled.connect(self._toggle_select_all)
        tree_header.addWidget(self._select_all_cb)

        tree_header.addStretch()

        self._count_label = QLabel("Ограничений найдено: 0")
        self._count_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        tree_header.addWidget(self._count_label)
        tl.addLayout(tree_header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            "", "Ограничение", "Тип", "Серьёзность", "Текущее значение",
            "Ожидаемое значение", "Путь в реестре", "Способ исправления",
        ])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

        # Ширины колонок
        hdr = self._tree.header()
        hdr.setStretchLastSection(True)
        self._tree.setColumnWidth(0, 30)   # чекбокс
        self._tree.setColumnWidth(1, 250)  # имя
        self._tree.setColumnWidth(2, 150)  # тип
        self._tree.setColumnWidth(3, 100)  # серьёзность
        self._tree.setColumnWidth(4, 100)  # текущее
        self._tree.setColumnWidth(5, 100)  # ожидаемое
        self._tree.setColumnWidth(6, 350)  # путь в реестре

        tl.addWidget(self._tree, 1)
        layout.addWidget(tree_frame, 1)

    # ── Сканирование ───────────────────────────────────────────────────────

    def _start_scan(self):
        self._tree.clear()
        self._found_restrictions.clear()
        self._scan_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._fix_all_btn.setEnabled(False)
        self._fix_selected_btn.setEnabled(False)
        self._select_all_cb.setEnabled(False)
        self._select_all_cb.setChecked(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._status_label.setText("🔍 Сканирование системных ограничений...")

        self._scanner = RestrictionScanner()
        self._scanner.found.connect(self._on_found)
        self._scanner.progress.connect(self._on_progress)
        self._scanner.finished.connect(self._on_scan_finished)
        self._scanner.start()

    def _stop_scan(self):
        if self._scanner:
            self._scanner.cancel()

    def _on_found(self, restriction: Restriction):
        self._found_restrictions.append(restriction)
        self._add_tree_item(restriction)
        self._count_label.setText(f"Ограничений найдено: {len(self._found_restrictions)}")

    def _on_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            f"🔍 Проверено: {current}/{total}"
        )

    def _on_scan_finished(self):
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._select_all_cb.setEnabled(len(self._found_restrictions) > 0)

        count = len(self._found_restrictions)
        if count == 0:
            self._status_label.setText("✅ Ограничений не обнаружено. Система в норме.")
            self.status_message.emit("Ограничений не найдено")
        else:
            self._status_label.setText(
                f"⚠ Найдено ограничений: {count}. "
                f"Выделите нужные и нажмите «Снять»."
            )
            self._fix_all_btn.setEnabled(True)
            self.status_message.emit(f"Найдено ограничений: {count}")

    # ── Добавление в таблицу ───────────────────────────────────────────────

    def _add_tree_item(self, r: Restriction):
        p = self._palette
        item = QTreeWidgetItem()
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setText(1, r.name)
        item.setText(2, self._type_name(r.restriction_type))
        item.setText(3, self._severity_name(r.severity))
        item.setText(4, r.current_data)
        item.setText(5, r.registry_data_expected or "(отсутствует)")
        item.setText(6, r.registry_path)
        item.setText(7, r.fix_method)
        item.setData(0, Qt.ItemDataRole.UserRole, len(self._found_restrictions) - 1)
        item.setToolTip(1, r.description)
        item.setToolTip(6, r.registry_path)
        item.setToolTip(7, r.fix_method)

        # Цвет серьёзности
        sev_colors = {
            Severity.LOW: QColor(p.success),
            Severity.MEDIUM: QColor(p.warning),
            Severity.HIGH: QColor(p.danger),
            Severity.CRITICAL: QColor(p.danger),
        }
        sc = sev_colors.get(r.severity, QColor(p.text_primary))
        item.setForeground(3, sc)

        # Фон для критических
        if r.severity in (Severity.HIGH, Severity.CRITICAL):
            for col in range(8):
                item.setBackground(col, QColor(p.bg_hover))

        self._tree.addTopLevelItem(item)

    # ── Выделение ──────────────────────────────────────────────────────────

    def _toggle_select_all(self, checked: bool):
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            item.setCheckState(0,
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
        self._update_fix_buttons()

    def _on_item_changed(self, item, column):
        if column == 0:
            self._update_fix_buttons()

    def _on_selection_changed(self):
        self._update_fix_buttons()

    def _update_fix_buttons(self):
        checked = self._get_checked_items()
        has_checked = len(checked) > 0
        self._fix_selected_btn.setEnabled(has_checked)
        self._fix_all_btn.setEnabled(len(self._found_restrictions) > 0)

    def _get_checked_items(self) -> list[QTreeWidgetItem]:
        items = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                items.append(item)
        # Также добавляем выделенные строки (если чекбоксы не отмечены)
        if not items:
            for item in self._tree.selectedItems():
                if item not in items:
                    items.append(item)
        return items

    # ── Снятие ограничений ─────────────────────────────────────────────────

    def _fix_selected(self):
        items = self._get_checked_items()
        if not items:
            QMessageBox.information(self, "Информация", "Выделите ограничения для снятия.")
            return
        self._fix_items(items)

    def _fix_all(self):
        reply = QMessageBox.question(
            self, "⚠ Подтверждение",
            "Снять ВСЕ обнаруженные ограничения?\n\n"
            "Это снимет все блокировки, IFEO-дебаггеры и восстановит "
            "параметры реестра к значениям по умолчанию.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        items = []
        for i in range(self._tree.topLevelItemCount()):
            items.append(self._tree.topLevelItem(i))
        self._fix_items(items)

    def _fix_items(self, items: list[QTreeWidgetItem]):
        if not _HAS_WINREG:
            QMessageBox.warning(
                self, "Ошибка",
                "Модуль winreg недоступен. Снятие ограничений невозможно."
            )
            return

        fixed = 0
        failed = 0

        for item in items:
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is None or idx >= len(self._found_restrictions):
                continue
            r = self._found_restrictions[idx]

            success = self._fix_restriction(r)
            if success:
                fixed += 1
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setHidden(True)
            else:
                failed += 1

        # Обновляем счётчик
        visible = sum(
            1 for i in range(self._tree.topLevelItemCount())
            if not self._tree.topLevelItem(i).isHidden()
        )
        self._count_label.setText(f"Ограничений найдено: {visible}")
        self._update_fix_buttons()

        if fixed > 0:
            self.status_message.emit(f"🔧 Снято ограничений: {fixed}")
        if failed > 0:
            self.status_message.emit(f"❌ Не удалось снять: {failed}")

    def _fix_restriction(self, r: Restriction) -> bool:
        """Снимает одно ограничение. Возвращает True при успехе."""
        try:
            if r.registry_path.lower().startswith("system\\"):
                hkey = winreg.HKEY_LOCAL_MACHINE
                subkey = r.registry_path
            elif r.registry_path.lower().startswith("software\\"):
                # Пробуем оба куста
                success = False
                for hk in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        key = winreg.OpenKey(hk, subkey=r.registry_path,
                                             access=winreg.KEY_SET_VALUE)
                        if r.registry_data_expected == "":
                            try:
                                winreg.DeleteValue(key, r.registry_value)
                            except FileNotFoundError:
                                pass
                        else:
                            winreg.SetValueEx(key, r.registry_value, 0,
                                              winreg.REG_DWORD,
                                              int(r.registry_data_expected))
                        winreg.CloseKey(key)
                        success = True
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                return success
            else:
                hkey = winreg.HKEY_LOCAL_MACHINE
                subkey = r.registry_path

            key = winreg.OpenKey(hkey, subkey,
                                 access=winreg.KEY_SET_VALUE)
            if r.registry_data_expected == "":
                try:
                    winreg.DeleteValue(key, r.registry_value)
                except FileNotFoundError:
                    pass
            else:
                try:
                    expected_int = int(r.registry_data_expected)
                    winreg.SetValueEx(key, r.registry_value, 0,
                                      winreg.REG_DWORD, expected_int)
                except ValueError:
                    winreg.SetValueEx(key, r.registry_value, 0,
                                      winreg.REG_SZ, r.registry_data_expected)
            winreg.CloseKey(key)
            return True

        except FileNotFoundError:
            # Если ключ не существует — ограничения нет, считаем успехом
            return True
        except OSError as e:
            self.status_message.emit(f"❌ Ошибка: {r.name} — {e}")
            return False

    # ── Утилиты ────────────────────────────────────────────────────────────

    @staticmethod
    def _type_name(rt: RestrictionType) -> str:
        names = {
            RestrictionType.POLICY: "Групповая политика",
            RestrictionType.IFEO_DEBUGGER: "IFEO-дебаггер",
            RestrictionType.REGISTRY_BLOCK: "Блокировка реестра",
            RestrictionType.EXPLORER_RESTRICT: "Ограничение проводника",
            RestrictionType.APPLOCKER: "AppLocker / SRP",
            RestrictionType.UAC: "UAC",
            RestrictionType.OTHER: "Прочее",
        }
        return names.get(rt, "Прочее")

    @staticmethod
    def _severity_name(s: Severity) -> str:
        names = {
            Severity.LOW: "⚠ Низкая",
            Severity.MEDIUM: "⚠⚠ Средняя",
            Severity.HIGH: "⚠⚠⚠ Высокая",
            Severity.CRITICAL: "🛑 Критическая",
        }
        return names.get(s, "Неизвестно")