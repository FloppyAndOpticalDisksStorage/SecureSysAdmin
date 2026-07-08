<p align="center">
  <img src="https://img.shields.io/badge/version-0.1--beta-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20|%20WinPE%20|%20WinRE-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-red?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/status-beta-orange?style=flat-square" alt="Status">
</p>

<h1 align="center">🛡 SecureSysAdmin</h1>

<p align="center">
  <strong>Инструмент системного администратора для выживания в скомпрометированной Windows</strong><br>
  Антивирусный сканер • Файловый проводник • Диспетчер задач • Снятие ограничений<br>
  <em>Работает в Windows, WinPE и WinRE</em>
</p>

---

## 📖 Оглавление

- [💡 Зачем это нужно](#-зачем-это-нужно)
- [📸 Скриншоты](#-скриншоты)
- [🧩 Возможности](#-возможности)
- [📦 Установка](#-установка)
- [🔧 Сборка в EXE](#-сборка-в-exe)
- [🖥 WinPE / WinRE](#-winpe--winre)
- [📁 Структура проекта](#-структура-проекта)
- [📋 Требования](#-требования)
- [📄 Лицензия](#-лицензия)

---

## 💡 Зачем это нужно

Когда Windows скомпрометирован — **диспетчер задач заблокирован**, **проводник не грузится**, **реестр перекрыт политиками**, а стандартные средства диагностики отключены. SecureSysAdmin — это **автономный набор инструментов**, который работает даже в среде восстановления (WinPE/WinRE) и не зависит от поломанных компонентов системы.

> 🎯 **Целевая аудитория:** системные администраторы, специалисты по кибербезопасности, incident response.

---

## 📸 Скриншоты

<!-- Замените ссылки на реальные скриншоты после снятия -->
<p align="center">
  <em>Скриншоты будут добавлены в ближайшее время</em>
</p>

---

## 🧩 Возможности

### 🛡 Сканер безопасности
| Функция | Описание |
|---------|----------|
| **Сигнатурный анализ** | Проверка файлов по хешам MD5/SHA256 |
| **Эвристический анализ** | Поиск подозрительных паттернов, строк PowerShell, URL |
| **PE-анализ** | Проверка PE-заголовков и цифровых подписей |
| **Карантин** | Перемещение угроз в `%SystemRoot%\SecureSysAdmin_Quarantine` |
| **Удаление** | `MoveFileEx(DELAY_UNTIL_REBOOT)` для занятых файлов |
| **Уровни угроз** | Safe / Suspicious / High / Critical |

### ⚡ Быстрые действия (30+ команд)
| Категория | Команды |
|-----------|---------|
| **Система** | `taskmgr`, `regedit`, `compmgmt.msc`, `rstrui`, `msinfo32`, `resmon`, `devmgmt.msc`, `services.msc` |
| **Сеть** | `ipconfig /all`, `ping 8.8.8.8`, `netstat -anob`, `tracert`, `nslookup` |
| **Диагностика** | `sfc /scannow`, `DISM /Online /Cleanup-Image /RestoreHealth`, `chkdsk`, `perfmon` |
| **Безопасность** | `lusrmgr.msc`, `gpedit.msc`, `secpol.msc`, `wf.msc`, `certlm.msc` |
| **Очистка** | `cleanmgr`, `mrt`, `temp` (очистка временных файлов) |
| **Обновление** | `appwiz.cpl`, `wuapp` (обновления), `taskschd.msc` |
| **Восстановление** | `rstrui`, `recoverydrive`, `sdclt` (бэкап) |

### 📁 Файловый проводник
- 🌲 Дерево файловой системы (на основе [`QFileSystemModel`](https://doc.qt.io/qt-6/qfilesystemmodel.html))
- ⚡ Быстрые переходы: диски + спецпапки (Desktop, Documents, Downloads, Windows, System32)
- 🧭 Навигационная строка с автодополнением
- 📄 Предпросмотр текстовых файлов
- 🖱 **Контекстное меню:** удалить, переименовать, создать папку, свойства, запуск от админа, сканировать на вирусы

### 📊 Диспетчер задач
- ⚡ Автообновление каждые 1.5 секунды
- 📋 Колонки: PID, имя, CPU%, память, статус, путь, пользователь
- 🔍 Фильтр по имени процесса
- 🖱 **Контекстное меню:** завершить процесс / дерево, приостановить / возобновить, изменить приоритет, открыть путь

### 🔓 Ограничения и дебаггеры
- 🔍 Сканирование **IFEO-дебаггеров** (18 процессов: `taskmgr.exe`, `regedit.exe`, `cmd.exe`, `powershell.exe`, `procexp.exe`, `wireshark.exe`, `ollydbg.exe`, `x64dbg.exe`, `ida.exe`, `windbg.exe` и др.)
- 🔍 Блокировки реестра (Task Manager, Regedit, CMD, Control Panel)
- 🔍 Ограничения проводника (NoRun, NoClose, NoDrives, NoViewContextMenu, NoChangingWallPaper)
- 🔍 Групповые политики (NoLogOff, HideClock, безопасный режим)
- 🔍 UAC (полное отключение, тихий режим)
- 🔧 **Снять выделенные** — выборочное снятие
- ⚡ **Снять все ограничения** — массовое восстановление

### ⚙ Настройки
- 🎨 Тёмная / светлая тема (мгновенное переключение)
- ✨ Анимации интерфейса (вкл/выкл + скорость)
- 📂 Путь сканирования по умолчанию
- 🗑 Путь карантина
- 📏 Максимальный размер сканируемого файла
- 🔄 Сброс к заводским настройкам

---

## 📦 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/YOUR_USERNAME/SecureSysAdmin.git
cd SecureSysAdmin
```

### 2. Установка зависимостей

```powershell
pip install -r requirements.txt
```

### 3. Запуск

```powershell
python main.py
```

---

## 🔧 Сборка в EXE

Для создания автономного `.exe` без зависимостей:

```powershell
pip install pyinstaller
pyinstaller SecureSysAdmin.spec
```

Готовый файл появится в `dist/SecureSysAdmin.exe`.

**Особенности собранного EXE:**
- Не требует установленного Python
- Все зависимости упакованы внутрь
- Чистый GUI (без консольного окна)
- При необходимости раскомментируйте `uac_admin=True` в [`SecureSysAdmin.spec`](SecureSysAdmin.spec) для автоматического запроса прав администратора

---

## 🖥 WinPE / WinRE

Приложение **спроектировано для запуска в среде восстановления**:

| Особенность | Реализация |
|-------------|-----------|
| ⚠ Отсутствие `pywin32` | Все импорты обёрнуты в `try/except` |
| ⚠ Отсутствие `psutil` | Диспетчер задач показывает сообщение о недоступности |
| 🔗 Нет зависимостей от реестра | Только чтение через `winreg` |
| 🎨 Стилизация | Полностью через QSS, не зависит от системной темы |
| 🔤 Шрифты | `Segoe UI` доступен в WinPE по умолчанию |
| 📦 Один EXE-файл | Легко скопировать на флешку / в WinPE-образ |

### Интеграция в WinPE-образ

Добавьте `SecureSysAdmin.exe` в `boot.wim` вашего WinPE:

```cmd
DISM /Mount-Image /ImageFile:C:\temp\boot.wim /Index:1 /MountDir:C:\temp\mount
copy SecureSysAdmin.exe C:\temp\mount\Windows\System32\
DISM /Unmount-Image /MountDir:C:\temp\mount /Commit
```

---

## 📁 Структура проекта

```
SecureSysAdmin/
├── main.py                          # Точка входа
├── requirements.txt                 # Зависимости
├── SecureSysAdmin.spec              # Конфиг PyInstaller
├── README.md                        # Этот файл
└── app/
    ├── __init__.py
    ├── main_window.py               # Главное окно + сайдбар + вкладка сканера
    ├── scanner/
    │   ├── __init__.py
    │   └── virus_scanner.py         # Сигнатурный + эвристический сканер
    ├── tabs/
    │   ├── __init__.py
    │   ├── quick_actions.py         # Быстрые действия (30+ команд)
    │   ├── file_explorer.py         # Файловый проводник
    │   ├── task_manager.py          # Диспетчер задач
    │   ├── restrictions.py          # Сканер ограничений и дебаггеров
    │   └── settings.py              # Настройки приложения
    └── utils/
        ├── __init__.py
        ├── theme.py                 # Тёмная/светлая палитры + QSS
        └── animations.py            # Анимации (fade, slide, pulse)
```

---

## 📋 Требования

| Модуль | Версия | Назначение |
|--------|--------|-----------|
| [`PyQt6`](https://pypi.org/project/PyQt6/) | ≥ 6.7.0 | GUI-фреймворк |
| [`psutil`](https://pypi.org/project/psutil/) | ≥ 5.9.0 | Мониторинг процессов |
| [`pywin32`](https://pypi.org/project/pywin32/) | ≥ 306 | Win32 API (PE, цифровые подписи) |
| [`requests`](https://pypi.org/project/requests/) | ≥ 2.31.0 | Резерв: облачные проверки |
| [`Pillow`](https://pypi.org/project/Pillow/) | ≥ 10.0.0 | Работа с изображениями |

**Минимальная версия Python:** 3.10+

---

## 📄 Лицензия

MIT License — делайте что угодно, just don't sue me.

---

<p align="center">
  <sub>Сделано с ❤️ для сисадминов, которые устали от заблокированных инструментов</sub>
</p>
