from __future__ import annotations

import ctypes
import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKED_SOURCES = (
    "src/main/java/cutoff/sort/MergeSort.java",
    "src/jmh/java/cutoff/bench/SortBench.java",
)
POWER_OVERLAYS = {
    "961cc777-2547-4f9d-8174-7d86181b8a7a": "best_power_efficiency",
    "00000000-0000-0000-0000-000000000000": "balanced",
    "ded574b5-45a0-4f42-8737-46345c09c238": "best_performance",
}

def command_output(*command: str) -> str:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {error}"
    return (result.stdout + result.stderr).strip()

def powershell_json(expression: str):
    output = command_output("powershell", "-NoProfile", "-Command", f"{expression} | ConvertTo-Json -Compress")
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return output

def windows_power() -> dict:
    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ac_line_status", ctypes.c_ubyte),
            ("battery_flag", ctypes.c_ubyte),
            ("battery_life_percent", ctypes.c_ubyte),
            ("system_status_flag", ctypes.c_ubyte),
            ("battery_life_time", ctypes.c_ulong),
            ("battery_full_life_time", ctypes.c_ulong),
        ]

    status = SystemPowerStatus()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
    power = {
        "ac_online": status.ac_line_status == 1,
        "battery_percent": status.battery_life_percent,
        "battery_saver_on": status.system_status_flag == 1,
        "active_scheme": command_output("powercfg", "/getactivescheme"),
    }

    overlay = ctypes.create_string_buffer(16)
    try:
        failed = ctypes.windll.powrprof.PowerGetEffectiveOverlayScheme(overlay)
    except (AttributeError, OSError):
        failed = 1
    if failed:
        power["power_mode"] = "unknown"
    else:
        guid = str(uuid.UUID(bytes_le=overlay.raw))
        power["power_mode"] = POWER_OVERLAYS.get(guid, guid)
    return power

def numpy_version() -> str:
    try:
        import numpy
    except ImportError:
        return "not installed"
    return numpy.__version__

def collect() -> dict:
    info = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "os": platform.platform(),
        "python": platform.python_version(),
        "numpy": numpy_version(),
        "java": command_output("java", "-version"),
        "sources_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in TRACKED_SOURCES
        },
    }
    if sys.platform == "win32":
        info["cpu"] = powershell_json(
            "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, "
            "NumberOfLogicalProcessors, MaxClockSpeed, L2CacheSize, L3CacheSize"
        )
        info["ram_bytes"] = powershell_json("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
        info["power"] = windows_power()
    return info

def main() -> int:
    text = json.dumps(collect(), indent=2, ensure_ascii=True)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0

if __name__ == "__main__":
    sys.exit(main())
