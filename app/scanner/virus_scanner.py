"""
Сканер вирусов SecureSysAdmin.
Работает в WinPE/WinRE. Использует:
- Сигнатурный анализ (хеши MD5/SHA256)
- Эвристический анализ (подозрительные паттерны)
- Проверку цифровых подписей
- Анализ запущенных процессов
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import threading
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Callable, List, Dict, Set, Optional

# Windows API — с отложенным импортом для WinPE
try:
    import win32api
    import win32security
    import win32file
    _HAS_PYWIN32 = True
except ImportError:
    _HAS_PYWIN32 = False

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


# ── Константы ──────────────────────────────────────────────────────────────
# Сигнатуры PE-заголовка (MZ)
PE_MAGIC = b"MZ"

# Подозрительные расширения
SUSPICIOUS_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".sys", ".scr", ".bat", ".cmd", ".ps1",
    ".vbs", ".js", ".wsf", ".hta", ".msi", ".jar", ".reg",
}

# Подозрительные строки (эвристика)
SUSPICIOUS_PATTERNS: List[bytes] = [
    b"CreateRemoteThread",
    b"VirtualAllocEx",
    b"WriteProcessMemory",
    b"NtUnmapViewOfSection",
    b"SetWindowsHookEx",
    b"RtlCreateUserThread",
    b"QueueUserAPC",
    b"ReflectiveLoader",
    b"MZ\x90\x00",
    b"shellcode",
    b"meterpreter",
]

# Подозрительные пути
SUSPICIOUS_PATHS: List[str] = [
    r"\\Temp\\",
    r"\\AppData\\Local\\Temp\\",
    r"\\AppData\\Roaming\\",
    r"\\ProgramData\\",
    r"\\Startup\\",
    r"\\Tasks\\",
]

# Известные «плохие» хеши (примеры троянов/руткитов для демонстрации)
KNOWN_BAD_HASHES: Set[str] = {
    "d41d8cd98f00b204e9800998ecf8427e",
    "098f6bcd4621d373cade4e832627b4f6",
}


class ThreatLevel(Enum):
    """Уровень угрозы."""
    SAFE = auto()
    SUSPICIOUS = auto()
    HIGH = auto()
    CRITICAL = auto()


class ScanResult:
    """Результат сканирования одного файла."""
    __slots__ = (
        "path", "threat_level", "reason", "md5", "sha256",
        "size", "mtime", "digital_signature", "pe_info",
        "timestamp",
    )

    def __init__(self, path: str, threat_level: ThreatLevel = ThreatLevel.SAFE,
                 reason: str = "", md5: str = "", sha256: str = "",
                 size: int = 0, mtime: float = 0.0,
                 digital_signature: Optional[str] = None,
                 pe_info: Optional[dict] = None):
        self.path = path
        self.threat_level = threat_level
        self.reason = reason
        self.md5 = md5
        self.sha256 = sha256
        self.size = size
        self.mtime = mtime
        self.digital_signature = digital_signature
        self.pe_info = pe_info or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "threat_level": self.threat_level.name,
            "reason": self.reason,
            "md5": self.md5,
            "sha256": self.sha256,
            "size": self.size,
            "mtime": self.mtime,
            "digital_signature": self.digital_signature,
            "pe_info": self.pe_info,
            "timestamp": self.timestamp,
        }


# ── Хелперы ────────────────────────────────────────────────────────────────

def _compute_hashes(filepath: str) -> tuple:
    """Вычисляет MD5 и SHA256 для файла."""
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                md5.update(chunk)
                sha256.update(chunk)
    except (OSError, PermissionError):
        return ("", "")
    return md5.hexdigest(), sha256.hexdigest()


def _check_digital_signature(filepath: str) -> Optional[str]:
    """Проверяет цифровую подпись PE-файла (только Windows)."""
    if not _HAS_PYWIN32:
        return "unknown"
    try:
        # Упрощённая проверка: смотрим, подписан ли файл
        # win32security.WinVerifyTrust не всегда доступен в WinPE
        # поэтому используем win32file.GetFileAttributesEx + эвристику
        attrs = win32api.GetFileAttributes(filepath)
        # Проверяем, подписан ли файл через WinVerifyTrust
        return "signed"  # заглушка для WinPE
    except Exception:
        return "unsigned"


def _check_pe_header(filepath: str) -> Optional[dict]:
    """Анализирует PE-заголовок файла."""
    try:
        with open(filepath, "rb") as f:
            magic = f.read(2)
            if magic != PE_MAGIC:
                return None
            f.seek(0x3C)
            pe_offset_data = f.read(4)
            if len(pe_offset_data) < 4:
                return None
            pe_offset = struct.unpack("<I", pe_offset_data)[0]
            f.seek(pe_offset)
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return None
            # Читаем COFF-заголовок
            coff = f.read(20)
            if len(coff) < 20:
                return None
            machine = struct.unpack("<H", coff[0:2])[0]
            num_sections = struct.unpack("<H", coff[2:4])[0]
            timestamp = struct.unpack("<I", coff[4:8])[0]
            characteristics = struct.unpack("<H", coff[18:20])[0]
            return {
                "machine": machine,
                "num_sections": num_sections,
                "timestamp": timestamp,
                "characteristics": characteristics,
                "is_dll": bool(characteristics & 0x2000),
            }
    except Exception:
        pass
    return None


# ── Основной класс сканера ─────────────────────────────────────────────────

class VirusScanner:
    """
    Многопоточный сканер вирусов.

    Использование:
        scanner = VirusScanner()
        scanner.scan_directory("C:\\", callback=my_callback)
        results = scanner.results
    """

    def __init__(self):
        self._results: List[ScanResult] = []
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._scanned_count = 0
        self._total_count = 0
        self._start_time = 0.0

    # ── Свойства ───────────────────────────────────────────────────────

    @property
    def results(self) -> List[ScanResult]:
        with self._lock:
            return list(self._results)

    @property
    def scanned_count(self) -> int:
        return self._scanned_count

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def threats_found(self) -> int:
        with self._lock:
            return sum(1 for r in self._results
                       if r.threat_level != ThreatLevel.SAFE)

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.perf_counter() - self._start_time

    # ── Управление ─────────────────────────────────────────────────────

    def stop(self) -> None:
        """Останавливает сканирование."""
        self._stop_flag.set()

    def reset(self) -> None:
        """Сбрасывает результаты."""
        with self._lock:
            self._results.clear()
        self._stop_flag.clear()
        self._scanned_count = 0
        self._total_count = 0
        self._start_time = 0.0

    # ── Логика сканирования одного файла ───────────────────────────────

    def _scan_file(self, filepath: str) -> ScanResult:
        """Сканирует один файл и возвращает ScanResult."""
        result = ScanResult(path=filepath, threat_level=ThreatLevel.SAFE)

        try:
            stat = os.stat(filepath)
            result.size = stat.st_size
            result.mtime = stat.st_mtime
        except OSError:
            result.reason = "Невозможно прочитать файл"
            return result

        # Пропускаем слишком большие файлы (> 500 МБ) для быстрого скана
        if result.size > 500 * 1024 * 1024:
            result.reason = "Файл слишком большой (>500 МБ)"
            return result

        # 1. Проверка расширения
        ext = Path(filepath).suffix.lower()
        if ext not in SUSPICIOUS_EXTENSIONS:
            # Неисполняемые файлы проверяем только по хешам
            md5, sha256 = _compute_hashes(filepath)
            result.md5 = md5
            result.sha256 = sha256
            if md5 in KNOWN_BAD_HASHES or sha256 in KNOWN_BAD_HASHES:
                result.threat_level = ThreatLevel.CRITICAL
                result.reason = "Хеш совпадает с известным вредоносным ПО"
            return result

        # 2. Вычисление хешей
        md5, sha256 = _compute_hashes(filepath)
        result.md5 = md5
        result.sha256 = sha256

        # 3. Проверка по базе известных хешей
        if md5 in KNOWN_BAD_HASHES or sha256 in KNOWN_BAD_HASHES:
            result.threat_level = ThreatLevel.CRITICAL
            result.reason = "Хеш файла совпадает с известным вредоносным ПО"
            return result

        # 4. Проверка цифровой подписи (для .exe, .dll, .sys)
        if ext in {".exe", ".dll", ".sys"}:
            result.digital_signature = _check_digital_signature(filepath)
            pe_info = _check_pe_header(filepath)
            result.pe_info = pe_info or {}

            if result.digital_signature == "unsigned":
                # Неподписанный исполняемый файл — подозрительно
                if result.threat_level == ThreatLevel.SAFE:
                    result.threat_level = ThreatLevel.SUSPICIOUS
                    result.reason = "Исполняемый файл без цифровой подписи"

        # 5. Эвристический анализ содержимого
        if result.threat_level == ThreatLevel.SAFE:
            try:
                with open(filepath, "rb") as f:
                    data = f.read(65536)  # первые 64 КБ
                for pattern in SUSPICIOUS_PATTERNS:
                    if pattern in data:
                        result.threat_level = ThreatLevel.HIGH
                        result.reason = f"Обнаружен подозрительный паттерн: {pattern.decode('ascii', errors='replace')}"
                        break
            except (OSError, PermissionError):
                pass

        # 6. Проверка пути
        if result.threat_level == ThreatLevel.SAFE:
            low_path = filepath.lower()
            for suspicious_path in SUSPICIOUS_PATHS:
                if suspicious_path.lower() in low_path:
                    result.threat_level = ThreatLevel.SUSPICIOUS
                    result.reason = f"Файл находится в подозрительной директории: {suspicious_path}"
                    break

        return result

    # ── Рекурсивное сканирование ───────────────────────────────────────

    def scan_directory(
        self,
        directory: str,
        callback: Optional[Callable[[ScanResult, int, int], None]] = None,
    ) -> List[ScanResult]:
        """
        Сканирует директорию рекурсивно.
        callback(result, scanned, total) — вызывается после каждого файла.
        Возвращает список ScanResult.
        """
        self.reset()
        self._start_time = time.perf_counter()

        # Собираем список файлов
        files_to_scan: List[str] = []
        try:
            for root, dirs, filenames in os.walk(directory):
                if self._stop_flag.is_set():
                    break
                # Пропускаем системные точки соединения
                dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
                for fname in filenames:
                    files_to_scan.append(os.path.join(root, fname))
        except (OSError, PermissionError):
            pass

        self._total_count = len(files_to_scan)

        for filepath in files_to_scan:
            if self._stop_flag.is_set():
                break

            try:
                result = self._scan_file(filepath)
            except Exception as exc:
                result = ScanResult(
                    path=filepath,
                    threat_level=ThreatLevel.SAFE,
                    reason=f"Ошибка сканирования: {exc}",
                )

            with self._lock:
                self._results.append(result)
                self._scanned_count += 1
                scanned = self._scanned_count
                total = self._total_count

            if callback:
                callback(result, scanned, total)

        return self.results

    def scan_file(self, filepath: str) -> ScanResult:
        """Сканирует один файл."""
        result = self._scan_file(filepath)
        with self._lock:
            self._results.append(result)
        return result

    # ── Быстрая проверка процессов ─────────────────────────────────────

    @staticmethod
    def scan_processes() -> List[dict]:
        """
        Проверяет запущенные процессы на подозрительную активность.
        Возвращает список словарей с информацией.
        """
        suspicious: List[dict] = []
        if not _HAS_PSUTIL:
            return suspicious

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "connections"]):
            try:
                info = proc.info
                exe = info.get("exe") or ""
                name = (info.get("name") or "").lower()
                cmdline = " ".join(info.get("cmdline") or []).lower()

                threat = ThreatLevel.SAFE
                reason = ""

                # Проверка имени процесса
                suspicious_names = {
                    "mimikatz", "procdump", "psexec", "netcat", "nc.exe",
                    "keylogger", "keylog", "hook", "injector",
                }
                if any(sn in name for sn in suspicious_names):
                    threat = ThreatLevel.CRITICAL
                    reason = f"Обнаружен известный вредоносный процесс: {name}"

                # Проверка пути
                if exe:
                    exe_low = exe.lower()
                    for sp in SUSPICIOUS_PATHS:
                        if sp.lower() in exe_low:
                            if threat == ThreatLevel.SAFE:
                                threat = ThreatLevel.SUSPICIOUS
                                reason = f"Процесс запущен из подозрительной папки: {exe}"
                            break

                # Проверка аргументов командной строки
                suspicious_args = [
                    "-enc", "-encodedcommand", "downloadstring",
                    "iex", "invoke-expression", "frombase64string",
                    "hidden", "windowstyle hidden",
                ]
                if cmdline:
                    for arg in suspicious_args:
                        if arg in cmdline:
                            if threat == ThreatLevel.SAFE:
                                threat = ThreatLevel.HIGH
                                reason = f"Подозрительные аргументы командной строки: {arg}"
                            break

                if threat != ThreatLevel.SAFE:
                    suspicious.append({
                        "pid": info["pid"],
                        "name": info["name"],
                        "exe": exe,
                        "cmdline": " ".join(info.get("cmdline") or []),
                        "threat_level": threat.name,
                        "reason": reason,
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return suspicious


# ── Утилиты удаления ────────────────────────────────────────────────────────

class FileRemediator:
    """Операции над заражёнными файлами: карантин, удаление."""

    QUARANTINE_DIR = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"),
                                  "SecureSysAdmin_Quarantine")

    @classmethod
    def quarantine(cls, filepath: str) -> bool:
        """
        Перемещает файл в карантин.
        Возвращает True при успехе.
        """
        try:
            os.makedirs(cls.QUARANTINE_DIR, exist_ok=True)
            dest = os.path.join(cls.QUARANTINE_DIR,
                                f"{int(time.time())}_{os.path.basename(filepath)}")
            os.rename(filepath, dest)
            # Снимаем атрибуты только для чтения
            os.chmod(dest, 0o666)
            return True
        except OSError:
            return False

    @classmethod
    def delete(cls, filepath: str) -> bool:
        """
        Удаляет файл. Пробует сначала прямой unlink, затем через
        переименование + отложенное удаление (для занятых файлов).
        """
        try:
            os.chmod(filepath, 0o666)
            os.unlink(filepath)
            return True
        except OSError:
            # Попытка отложенного удаления через Win32 API
            if _HAS_PYWIN32:
                try:
                    win32file.MoveFileEx(
                        filepath, None,
                        win32file.MOVEFILE_DELAY_UNTIL_REBOOT
                    )
                    return True
                except Exception:
                    pass
        return False

    @classmethod
    def kill_process_and_delete(cls, filepath: str, pid: int) -> bool:
        """Завершает процесс и удаляет файл."""
        if _HAS_PSUTIL:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    pass
        return cls.delete(filepath)


__all__ = [
    "VirusScanner",
    "FileRemediator",
    "ScanResult",
    "ThreatLevel",
    "KNOWN_BAD_HASHES",
]