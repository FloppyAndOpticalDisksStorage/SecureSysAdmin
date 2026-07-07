"""
SecureSysAdmin — точка входа.
Запускается в Windows, WinPE и WinRE.
"""

if __name__ == "__main__":
    import sys
    import os

    # Добавляем корень проекта в PYTHONPATH
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from PyQt6.QtCore import Qt, QLocale
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtGui import QFont

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("SecureSysAdmin")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SecureSysAdmin")

    # Устанавливаем шрифт по умолчанию (Segoe UI доступен в WinPE/WinRE)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Пытаемся загрузить основной модуль
    try:
        from app.main_window import MainWindow
        window = MainWindow()
        window.show()
    except Exception as e:
        QMessageBox.critical(
            None, "Ошибка запуска",
            f"Не удалось запустить SecureSysAdmin:\n\n{e}\n\n"
            f"Убедитесь, что установлены все зависимости:\n"
            f"pip install -r requirements.txt"
        )
        sys.exit(1)

    sys.exit(app.exec())