from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
TEMPLATE = ROOT / "installer.iss.in"
OUTPUT_SCRIPT = ROOT / "installer.iss"


def read_version() -> str:
    version_file = ROOT / "src" / "pydm" / "version.py"
    namespace = {}
    exec(version_file.read_text(encoding="utf-8"), namespace)
    return str(namespace["__version__"])


def read_app_name() -> str:
    version_file = ROOT / "src" / "pydm" / "version.py"
    namespace = {}
    exec(version_file.read_text(encoding="utf-8"), namespace)
    return str(namespace.get("__app_name__", "PyDM"))


def find_iscc() -> str:
    candidates = []
    for env_var in ("ISCC", "ISCC_EXE"):
        value = os.environ.get(env_var)
        if value:
            candidates.append(value)

    candidates.extend([
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ])

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)

    raise FileNotFoundError("Inno Setup compiler (ISCC.exe) was not found")


def build_installer() -> None:
    version = read_version()
    app_name = read_app_name()
    portable_name = f"PyDM-v{version}-Windows-x64-Portable"
    portable_dir = DIST / portable_name
    installer_name = f"PyDM-v{version}-Windows-x64-Installer"

    if not portable_dir.exists():
        raise FileNotFoundError(f"Portable folder not found: {portable_dir}")

    if not any(portable_dir.iterdir()):
        raise FileNotFoundError(f"Portable folder is empty: {portable_dir}")

    # Prepare version for file metadata: ensure four components (major.minor.build.revision)
    parts = version.split('.') if version else []
    while len(parts) < 4:
        parts.append('0')
    version_file = '.'.join(parts[:4])

    template_text = TEMPLATE.read_text(encoding="utf-8")
    rendered = (
        template_text.replace("@APP_NAME@", app_name)
        .replace("@VERSION@", version)
        .replace("@VERSION_FILE@", version_file)
        .replace("@PORTABLE_DIR@", str(portable_dir.resolve()).replace("\\", "\\\\"))
    )
    OUTPUT_SCRIPT.write_text(rendered, encoding="utf-8")

    iscc = find_iscc()
    subprocess.run([iscc, str(OUTPUT_SCRIPT)], cwd=str(ROOT), check=True)

    output_exe = DIST / f"{installer_name}.exe"
    if not output_exe.exists():
        raise FileNotFoundError(f"Installer was not produced: {output_exe}")

    print(f"Created {output_exe}")


if __name__ == "__main__":
    build_installer()
