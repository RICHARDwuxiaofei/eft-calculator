"""Fresh/legacy/corrupt packaged EXE checks, rendered offscreen with isolated user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from legacy_db_smoke import assert_repaired, create_legacy_database

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"artifacts/audit-2026-10-25/windows-runtime"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    name = "TarkovArmorSimulatorDiagnostic" if args.diagnostic else "TarkovArmorSimulator"
    exe = ROOT/"dist"/name/f"{name}.exe"
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for case in ("fresh", "legacy", "corrupt"):
        with tempfile.TemporaryDirectory(prefix="eft-exe-audit-") as tmp:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LOCALAPPDATA=tmp,
                       EFT_TEST_SETTINGS_DIRECTORY=tmp, EFT_LOG_DIRECTORY=str(Path(tmp)/"logs"),
                       EFT_CALCULATOR_LANG="zh_CN", EFT_SMOKE_SCREENSHOT=str(OUT/f"{case}.png"))
            database = Path(tmp)/"TarkovArmorSimulator/current.sqlite3"
            if case == "legacy":
                create_legacy_database(database)
            elif case == "corrupt":
                database.parent.mkdir(parents=True)
                database.write_bytes(b"corrupt-database-original-retained")
            # The Windows GUI-subsystem EXE renders through Qt's offscreen platform.
            result = subprocess.run([str(exe), "--smoke-test"], check=False, env=env, cwd=ROOT,
                                    timeout=90, capture_output=True)
            assert result.returncode == 0, (case, result.returncode, result.stderr)
            assert (OUT/f"{case}.png").exists()
            if case == "legacy":
                assert_repaired(database)
                assert database.with_name(database.name+".before-legacy-repair.bak").exists()
            if case == "corrupt":
                copies = list(database.parent.glob("*.corrupt-*.bak"))
                assert len(copies) == 1
                assert copies[0].read_bytes() == b"corrupt-database-original-retained"
            connection = sqlite3.connect(database)
            try:
                assert connection.execute("SELECT count(*) FROM ammo").fetchone()[0] >= 184
            finally:
                connection.close()
            results.append({"case":case,"exit_code":result.returncode,"rendered_screenshot":f"{case}.png", "isolated":True})
    (OUT/"results.json").write_text(json.dumps({"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),"results":results},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
