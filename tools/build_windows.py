from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    app_name = "TarkovArmorSimulatorDiagnostic" if args.diagnostic else "TarkovArmorSimulator"
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    work = root / "build" / "pyinstaller"
    resources = root / "src" / "tarkov_armor_sim" / "resources"
    app_icon = resources / "icons" / "app-icon.ico"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--console" if args.diagnostic else "--windowed",
        "--name",
        app_name,
        "--paths",
        str(root / "src"),
        "--paths",
        str(root / "shared" / "tarkov_sim_core" / "src"),
        "--icon",
        str(app_icon),
        "--add-data",
        f"{resources};tarkov_armor_sim/resources",
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        "--specpath",
        str(root / "packaging"),
        str(root / "tools" / "launcher.py"),
    ]
    # Collect dependencies from this Python and Windows only. An unrelated tool's
    # ICU/OpenSSL DLL on PATH can otherwise be bundled in place of Qt's system ICU.
    environment = dict(os.environ)
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join(str(path) for path in (
        Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows,
    ))
    result = subprocess.run(command, cwd=root, env=environment, check=False)
    if result.returncode == 0:
        readme = root / "README.md"
        target = dist / app_name / "README.md"
        shutil.copy2(readme, target)
        print(f"Built: {dist / app_name}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
