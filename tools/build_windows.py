from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    work = root / "build" / "pyinstaller"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "TarkovArmorSimulator",
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

