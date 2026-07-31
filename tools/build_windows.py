from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
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
        "--windowed",
        "--name",
        "TarkovArmorSimulator",
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
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode == 0:
        readme = root / "README.md"
        target = dist / "TarkovArmorSimulator" / "README.md"
        shutil.copy2(readme, target)
        print(f"Built: {dist / 'TarkovArmorSimulator'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
