"""
Вкладка настроек приложения SecureSysAdmin.
Тема, анимации, язык, пути, сброс конфигурации.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QCheckBox, QSpinBox, QLineEdit,
    QScrollArea, QFrame, QMessageBox, QFileDialog,
)
from PyQt6.QtGui import QFont

from app.utils.animations import set_animations_enabled, animations_enabled
from app.utils.theme import ColorPalette, PALETTES


SETTINGS_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "SecureSysAdmin",
    "settings.json",
)


@dataclass
class AppSettings:
    """Датакласс настроек приложения."""
    theme: str = "dark"
    animations_enabled: bool = True
    animation_speed: int = 5  # 1–10
    language: str = "ru"
    scan_default_path: str = "C:\\"
    scan_exclude_system: bool = False
    max_file_size_mb: int = 500
    quarantine_path: str = ""
    auto_refresh_tasks: bool = True
    confirm_delete: bool = True

    def save(self):
        """Сохраняет настройки в JSON-файл."""
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> AppSettings:
        """Загружает настройки из JSON-файла или возвращает значения по умолчанию."""
        if not os.path.isfile(SETTINGS_FILE):
            return cls()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()


class SettingsTab(QWidget):
    """Вкладка настроек."""

    settings_changed = pyqtSignal(AppSettings)  # глобальные настройки изменились
    theme_changed = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._settings = AppSettings.load()
        self._setup_ui()
        self._load_settings_to_ui()

    def _setup_ui(self):
        p = self._palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Заголовок ──────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("⚙ Настройки")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        header.addWidget(title)
        header.addStretch()

        # Кнопки сохранения/сброса
        self._save_btn = QPushButton("💾 Сохранить")
        self._save_btn.setProperty("accent", True)
        self._save_btn.clicked.connect(self._save_settings)

        self._reset_btn = QPushButton("↺ Сбросить")
        self._reset_btn.setProperty("small", True)
        self._reset_btn.clicked.connect(self._reset_settings)

        header.addWidget(self._save_btn)
        header.addWidget(self._reset_btn)
        layout.addLayout(header)

        # ── Скролл-область ─────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(container)
        cl.setSpacing(16)

        # ── Группа: Внешний вид ────────────────────────────────────────
        appearance = QGroupBox("🎨 Внешний вид")
        appearance.setStyleSheet(self._group_style(p))
        ag = QVBoxLayout(appearance)
        ag.setSpacing(10)

        # Тема
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Тема оформления:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("🌙 Тёмная (Dark)", "dark")
        self._theme_combo.addItem("☀ Светлая (Light)", "light")
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        ag.addLayout(theme_row)

        # Анимации
        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Анимации:"))
        self._anim_cb = QCheckBox("Включить плавные анимации")
        self._anim_cb.setChecked(self._settings.animations_enabled)
        anim_row.addWidget(self._anim_cb)
        anim_row.addStretch()
        ag.addLayout(anim_row)

        # Скорость анимаций
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Скорость анимаций:"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(1, 10)
        self._speed_spin.setValue(self._settings.animation_speed)
        self._speed_spin.setToolTip("1 = очень быстро, 10 = медленно")
        self._speed_spin.setSuffix(" / 10")
        speed_row.addWidget(self._speed_spin)
        speed_row.addStretch()
        ag.addLayout(speed_row)

        cl.addWidget(appearance)

        # ── Группа: Сканер ─────────────────────────────────────────────
        scanner = QGroupBox("🛡 Сканер безопасности")
        scanner.setStyleSheet(self._group_style(p))
        sg = QVBoxLayout(scanner)
        sg.setSpacing(10)

        # Путь по умолчанию
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Путь сканирования по умолчанию:"))
        self._scan_path_edit = QLineEdit()
        self._scan_path_edit.setPlaceholderText("C:\\")
        self._scan_path_edit.setText(self._settings.scan_default_path)
        path_row.addWidget(self._scan_path_edit, 1)
        browse_btn = QPushButton("📂")
        browse_btn.setProperty("small", True)
        browse_btn.clicked.connect(self._browse_scan_path)
        path_row.addWidget(browse_btn)
        sg.addLayout(path_row)

        # Макс. размер файла
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Макс. размер файла (МБ):"))
        self._max_size_spin = QSpinBox()
        self._max_size_spin.setRange(10, 5000)
        self._max_size_spin.setSingleStep(50)
        self._max_size_spin.setValue(self._settings.max_file_size_mb)
        self._max_size_spin.setSuffix(" МБ")
        size_row.addWidget(self._max_size_spin)
        size_row.addStretch()
        sg.addLayout(size_row)

        # Исключать системные
        self._exclude_system_cb = QCheckBox("Пропускать системные папки (Windows, Program Files)")
        self._exclude_system_cb.setChecked(self._settings.scan_exclude_system)
        sg.addWidget(self._exclude_system_cb)

        cl.addWidget(scanner)

        # ── Группа: Карантин ───────────────────────────────────────────
        quarantine = QGroupBox("🔒 Карантин")
        quarantine.setStyleSheet(self._group_style(p))
        qg = QVBoxLayout(quarantine)
        qg.setSpacing(10)

        qpath_row = QHBoxLayout()
        qpath_row.addWidget(QLabel("Папка карантина:"))
        self._quarantine_edit = QLineEdit()
        self._quarantine_edit.setPlaceholderText(
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SecureSysAdmin_Quarantine")
        )
        self._quarantine_edit.setText(self._settings.quarantine_path)
        qpath_row.addWidget(self._quarantine_edit, 1)
        qbrowse_btn = QPushButton("📂")
        qbrowse_btn.setProperty("small", True)
        qbrowse_btn.clicked.connect(self._browse_quarantine_path)
        qpath_row.addWidget(qbrowse_btn)
        qg.addLayout(qpath_row)

        open_quarantine = QPushButton("📁 Открыть папку карантина")
        open_quarantine.setProperty("small", True)
        open_quarantine.clicked.connect(self._open_quarantine)
        qg.addWidget(open_quarantine)

        cl.addWidget(quarantine)

        # ── Группа: Интерфейс ─────────────────────────────────────────
        interface = QGroupBox("🖥 Интерфейс")
        interface.setStyleSheet(self._group_style(p))
        ig = QVBoxLayout(interface)
        ig.setSpacing(10)

        self._confirm_delete_cb = QCheckBox("Запрашивать подтверждение при удалении файлов")
        self._confirm_delete_cb.setChecked(self._settings.confirm_delete)
        ig.addWidget(self._confirm_delete_cb)

        self._auto_refresh_cb = QCheckBox("Автообновление диспетчера задач")
        self._auto_refresh_cb.setChecked(self._settings.auto_refresh_tasks)
        ig.addWidget(self._auto_refresh_cb)

        cl.addWidget(interface)

        # ── Группа: О программе ───────────────────────────────────────
        about = QGroupBox("ℹ О программе")
        about.setStyleSheet(self._group_style(p))
        ag2 = QVBoxLayout(about)

        info_text = QLabel(
            "<b>SecureSysAdmin v1.0</b><br><br>"
            "Инструмент системного администратора для работы в WinPE/WinRE.<br>"
            "Включает сканер безопасности, файловый проводник, "
            "диспетчер задач и быстрые команды.<br><br>"
            "<i>Разработано для offline-диагностики и восстановления систем Windows.</i>"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(f"color: {p.text_secondary};")
        ag2.addWidget(info_text)

        cl.addWidget(about)
        cl.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    # ── Методы ─────────────────────────────────────────────────────────────

    def _group_style(self, p: ColorPalette) -> str:
        return f"""
            QGroupBox {{
                color: {p.text_secondary};
                font-weight: bold;
                border: 1px solid {p.border};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 20px;
                padding-bottom: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """

    def _load_settings_to_ui(self):
        """Загружает сохранённые настройки в UI."""
        s = self._settings
        idx = self._theme_combo.findData(s.theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._anim_cb.setChecked(s.animations_enabled)
        self._speed_spin.setValue(s.animation_speed)
        self._scan_path_edit.setText(s.scan_default_path)
        self._max_size_spin.setValue(s.max_file_size_mb)
        self._exclude_system_cb.setChecked(s.scan_exclude_system)
        self._quarantine_edit.setText(s.quarantine_path)
        self._confirm_delete_cb.setChecked(s.confirm_delete)
        self._auto_refresh_cb.setChecked(s.auto_refresh_tasks)

    def _on_theme_changed(self, idx: int):
        """Предпросмотр темы при переключении комбобокса."""
        theme_name = self._theme_combo.currentData()
        if theme_name:
            self.theme_changed.emit(theme_name)
            self._palette = PALETTES.get(theme_name, self._palette)

    def _save_settings(self):
        """Сохраняет настройки из UI в датакласс и на диск."""
        s = self._settings
        s.theme = self._theme_combo.currentData() or "dark"
        s.animations_enabled = self._anim_cb.isChecked()
        s.animation_speed = self._speed_spin.value()
        s.scan_default_path = self._scan_path_edit.text().strip() or "C:\\"
        s.max_file_size_mb = self._max_size_spin.value()
        s.scan_exclude_system = self._exclude_system_cb.isChecked()
        s.quarantine_path = self._quarantine_edit.text().strip()
        s.confirm_delete = self._confirm_delete_cb.isChecked()
        s.auto_refresh_tasks = self._auto_refresh_cb.isChecked()

        s.save()

        # Применяем глобальные настройки
        set_animations_enabled(s.animations_enabled)

        self.settings_changed.emit(s)
        self.status_message.emit("✅ Настройки сохранены")

    def _reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию."""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Сбросить все настройки к значениям по умолчанию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._settings = AppSettings()
        self._load_settings_to_ui()
        self._settings.save()
        self.status_message.emit("↺ Настройки сброшены")

    def _browse_scan_path(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку сканирования")
        if path:
            self._scan_path_edit.setText(path)

    def _browse_quarantine_path(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку карантина")
        if path:
            self._quarantine_edit.setText(path)

    def _open_quarantine(self):
        qpath = self._quarantine_edit.text().strip()
        if not qpath:
            qpath = os.path.join(
                os.environ.get("SystemRoot", "C:\\Windows"),
                "SecureSysAdmin_Quarantine"
            )
        if os.path.isdir(qpath):
            import subprocess
            subprocess.Popen(["explorer.exe", qpath])
        else:
            QMessageBox.information(self, "Информация", "Папка карантина пока не создана.")