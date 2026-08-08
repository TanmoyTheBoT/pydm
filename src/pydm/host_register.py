import json
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import winreg  # type: ignore
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


DEFAULT_ALLOWED_ORIGINS = [
    "chrome-extension://bkibiddbjjhkbcfbfnipeikbcibaolec/",
]


def get_app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if base:
                return Path(base) / "PyDM"
        return Path.home() / ".pydm"

    return Path.home() / ".config" / "pydm"


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_app_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_project_root()


def get_manifest_path(base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        if getattr(sys, "frozen", False):
            base_dir = get_app_root_dir()
        else:
            base_dir = get_project_root() / "native"
    return Path(base_dir) / "com.pydm.host.json"


def get_host_path(base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        base_dir = get_app_root_dir()
    return Path(base_dir) / "pydm-host.exe"


def get_host_command() -> List[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--native-host"]
    return [sys.executable, "-m", "pydm.app", "--native-host"]


def write_manifest(manifest_path: Path, host_path: Path, allowed_origins: Optional[Iterable[str]] = None) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    host_path_value = host_path.name

    payload = {
        "name": "com.pydm.host",
        "description": "PyDM Native Messaging Host",
        "path": host_path_value,
        "type": "stdio",
        "allowed_origins": list(allowed_origins or DEFAULT_ALLOWED_ORIGINS),
    }

    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def install_browser_host(
    manifest_path: Optional[Path] = None,
    host_path: Optional[Path] = None,
    host_executable: Optional[Path] = None,
    allowed_origins: Optional[Iterable[str]] = None,
    write_registry: bool = True,
) -> dict:
    manifest_path = manifest_path or get_manifest_path()
    if host_executable is not None:
        host_path = Path(host_executable)
    else:
        host_path = host_path or get_host_path()

    # Default to the application folder for both manifest and host path.
    if manifest_path is None:
        manifest_path = get_manifest_path()
    if host_path is None:
        host_path = get_host_path()

    write_manifest(manifest_path, host_path, allowed_origins=allowed_origins)

    registry_entries = []
    if write_registry and sys.platform == "win32" and winreg is not None:
        for browser_name, subkey in (
            ("Chrome", r"Software\Google\Chrome\NativeMessagingHosts\com.pydm.host"),
            ("Edge", r"Software\Microsoft\Edge\NativeMessagingHosts\com.pydm.host"),
        ):
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey) as key:  # type: ignore[attr-defined]
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))  # type: ignore[attr-defined]
                registry_entries.append(browser_name)
            except OSError as exc:  # pragma: no cover - platform specific
                registry_entries.append(f"{browser_name}:error:{exc}")

    return {
        "manifest_path": str(manifest_path),
        "host_path": str(host_path),
        "registry": registry_entries,
    }


def ensure_browser_host_registered() -> dict:
    return install_browser_host()
