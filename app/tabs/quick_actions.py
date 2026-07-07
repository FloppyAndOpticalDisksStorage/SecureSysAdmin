"""
Вкладка «Быстрые действия» — панель быстрых команд сисадмина.
Запуск/остановка служб, сетевые утилиты, системные команды.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QProcess, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QScrollArea, QFrame, QGridLayout,
    QMessageBox, QApplication, QProgressBar,
)
from PyQt6.QtGui import QFont, QTextCursor

from app.utils.animations import pulse
from app.utils.theme import ColorPalette


class CommandButton(QPushButton):
    """Кнопка быстрой команды с индикацией выполнения."""
    command_requested = pyqtSignal(str, str)  # (label, command)

    def __init__(self, label: str, command: str, description: str = "",
                 palette: ColorPalette | None = None, parent=None):
        super().__init__(label, parent)
        self._command = command
        self._description = description
        self._palette = palette
        self.setToolTip(description or command)
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: self.command_requested.emit(label, command))


class QuickActionsTab(QWidget):
    """Вкладка с быстрыми командами."""

    # Сигнал: запрос на выполнение команды (метка, команда)
    execute_command = pyqtSignal(str, str)

    def __init__(self, palette: ColorPalette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._process: QProcess | None = None
        self._setup_ui()

    def _setup_ui(self):
        p = self._palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Заголовок ──────────────────────────────────────────────────
        title = QLabel("⚡ Быстрые действия")
        title.setProperty("heading", True)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(title)

        subtitle = QLabel("Выполнение системных команд и утилит")
        subtitle.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        layout.addWidget(subtitle)

        # ── Скролл-область с кнопками ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QVBoxLayout(container)
        grid.setSpacing(12)

        # ── Группа: Система ────────────────────────────────────────────
        sys_group = self._make_group("💻 Система", [
            ("Диспетчер задач", "taskmgr.exe", "Запустить диспетчер задач Windows"),
            ("Управление компьютером", "compmgmt.msc", "Управление дисками, службами, событиями"),
            ("Редактор реестра", "regedit.exe", "Запустить редактор реестра"),
            ("Консоль восстановления", "rstrui.exe", "Запустить восстановление системы"),
            ("Монитор ресурсов", "resmon.exe", "Запустить монитор ресурсов"),
            ("Сведения о системе", "msinfo32.exe", "Информация об оборудовании и ОС"),
        ])
        grid.addWidget(sys_group)

        # ── Группа: Сеть ───────────────────────────────────────────────
        net_group = self._make_group("🌐 Сетевые утилиты", [
            ("ipconfig /all", "ipconfig /all", "Полная информация о сетевых адаптерах"),
            ("Сброс DNS", "ipconfig /flushdns", "Очистить кэш DNS"),
            ("Обновить IP", "ipconfig /renew", "Обновить IP-адрес"),
            ("Таблица ARP", "arp -a", "Показать ARP-таблицу"),
            ("Сетевые подключения", "netstat -anob", "Активные подключения с PID"),
            ("Маршрутизация", "route print", "Таблица маршрутизации"),
            ("Ping Google", "ping -n 4 8.8.8.8", "Проверка интернет-соединения"),
            ("Трассировка", "tracert 8.8.8.8", "Трассировка маршрута"),
        ])
        grid.addWidget(net_group)

        # ── Группа: Диагностика ────────────────────────────────────────
        diag_group = self._make_group("🔧 Диагностика", [
            ("SFC Scan", "sfc /scannow", "Проверка целостности системных файлов"),
            ("DISM Check", "dism /online /cleanup-image /scanhealth",
             "Проверка образа Windows"),
            ("DISM Restore", "dism /online /cleanup-image /restorehealth",
             "Восстановление образа Windows"),
            ("CHKDSK (только инфо)", "chkdsk C:", "Проверка диска (без исправления)"),
            ("Службы Win", "services.msc", "Оснастка служб Windows"),
            ("Просмотр событий", "eventvwr.msc", "Журналы событий Windows"),
        ])
        grid.addWidget(diag_group)

        # ── Группа: Пользователи/Безопасность ──────────────────────────
        sec_group = self._make_group("🔒 Безопасность", [
            ("Локальные пользователи", "lusrmgr.msc", "Управление локальными пользователями"),
            ("Групповые политики", "gpedit.msc", "Редактор локальной групповой политики"),
            ("Брандмауэр", "wf.msc", "Windows Firewall с повышенной безопасностью"),
            ("Сертификаты", "certlm.msc", "Сертификаты локального компьютера"),
        ])
        grid.addWidget(sec_group)

        # ── Группа: Очистка / Восстановление ───────────────────────────
        clean_group = self._make_group("🧹 Очистка и восстановление", [
            ("Очистка диска", "cleanmgr.exe", "Освобождение места на диске"),
            ("Очистка Temp", "cmd /c del /q /f /s %TEMP%\\*",
             "Очистить временные файлы пользователя"),
            ("Очистка Prefetch", "cmd /c del /q /f C:\\Windows\\Prefetch\\*",
             "Очистить Prefetch"),
            ("Mrt (зловреды)", "mrt.exe", "Запустить Microsoft Malicious Removal Tool"),
        ])
        grid.addWidget(clean_group)

        grid.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # ── Консоль вывода ─────────────────────────────────────────────
        console_group = QGroupBox("📋 Консоль вывода")
        console_group.setStyleSheet(f"""
            QGroupBox {{
                color: {p.text_secondary};
                font-weight: bold;
                border: 1px solid {p.border};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """)
        console_layout = QVBoxLayout(console_group)

        # Кнопки управления консолью
        btn_row = QHBoxLayout()
        self._clear_btn = QPushButton("🗑 Очистить")
        self._clear_btn.setProperty("small", True)
        self._clear_btn.clicked.connect(self._clear_output)
        self._copy_btn = QPushButton("📋 Копировать")
        self._copy_btn.setProperty("small", True)
        self._copy_btn.clicked.connect(self._copy_output)
        self._stop_btn = QPushButton("⏹ Остановить")
        self._stop_btn.setProperty("small", True)
        self._stop_btn.setProperty("danger", True)
        self._stop_btn.clicked.connect(self._stop_process)
        self._stop_btn.setEnabled(False)

        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._copy_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        console_layout.addLayout(btn_row)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setStyleSheet(f"""
            QTextEdit {{
                background-color: {p.terminal_bg};
                color: {p.terminal_text};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 8px;
                font-family: "Consolas", "Courier New", monospace;
            }}
        """)
        self._output.setMinimumHeight(150)
        self._output.append(
            '<span style="color:#959da5;">Готов к выполнению команд. '
            'Нажмите кнопку выше для запуска.</span>'
        )
        console_layout.addWidget(self._output)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximum(0)  # бесконечный
        console_layout.addWidget(self._progress)

        layout.addWidget(console_group)

        # Подключаем сигналы кнопок к выполнению команд
        self._connect_command_buttons(container)

    def _make_group(self, title: str, commands: list[tuple[str, str, str]]) -> QGroupBox:
        """Создаёт QGroupBox с сеткой кнопок."""
        p = self._palette
        group = QGroupBox(title)
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {p.text_secondary};
                font-weight: bold;
                border: 1px solid {p.border};
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """)
        gl = QGridLayout(group)
        gl.setSpacing(6)

        cols = 3
        for i, (label, cmd, desc) in enumerate(commands):
            btn = CommandButton(label, cmd, desc, p)
            gl.addWidget(btn, i // cols, i % cols)

        return group

    def _connect_command_buttons(self, container: QWidget):
        """Рекурсивно подключает сигналы CommandButton к выполнению."""
        for child in container.findChildren(CommandButton):
            child.command_requested.connect(self._run_command)

    # ── Выполнение команд ─────────────────────────────────────────────────

    def _run_command(self, label: str, command: str):
        """Запускает команду и выводит результат."""
        self._output.append(
            f'\n<span style="color:{self._palette.accent_primary};">'
            f'▶ [{label}]</span> '
            f'<span style="color:{self._palette.text_secondary};">{command}</span>'
        )
        self._scroll_to_bottom()
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)

        self.execute_command.emit(label, command)

        # Запуск через QProcess
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        if command.startswith("cmd /c "):
            self._process.start("cmd.exe", ["/c", command[7:]])
        else:
            parts = command.split(" ", 1)
            prog = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            self._process.start(prog, args)

        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def _on_output(self):
        if self._process:
            data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            self._output.insertPlainText(data)
            self._scroll_to_bottom()

    def _on_finished(self, exit_code):
        color = self._palette.success if exit_code == 0 else self._palette.warning
        self._output.append(
            f'<span style="color:{color};">'
            f'⏹ Процесс завершён с кодом {exit_code}</span>'
        )
        self._scroll_to_bottom()
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)

    def _on_error(self, error):
        self._output.append(
            f'<span style="color:{self._palette.danger};">'
            f'❌ Ошибка запуска: {error}</span>'
        )
        self._scroll_to_bottom()
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)

    def _stop_process(self):
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _clear_output(self):
        self._output.clear()
        self._output.append(
            f'<span style="color:{self._palette.text_secondary};">'
            f'Готов к выполнению команд.</span>'
        )

    def _copy_output(self):
        text = self._output.toPlainText()
        QApplication.clipboard().setText(text)

    def _scroll_to_bottom(self):
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._output.setTextCursor(cursor)