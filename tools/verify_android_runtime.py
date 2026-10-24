"""ADB-only acceptance on a dedicated headless emulator; never targets a personal device."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"artifacts/audit-2026-10-25/android-runtime"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", default="emulator-5580")
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--night", choices=("yes", "no"), default="no")
    args = parser.parse_args()
    assert args.serial == "emulator-5580", "Dedicated audit emulator only"
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    def adb(*values):
        result = subprocess.run([args.adb,"-s",args.serial,*values],check=False,capture_output=True,timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout

    apk = args.apk or ROOT/"android/app/build/outputs/apk/debug/app-debug.apk"
    adb("install","-r",str(apk))
    adb("shell","cmd","uimode","night",args.night)
    receipts = []
    for locale in ("zh-CN","en-US"):
        adb("shell","cmd","locale","set-app-locales","com.eftcalculator","--user","0","--locales",locale)
        for name,size,density in (("portrait","1080x1920","480"),("landscape","1920x1080","320"),("narrow","720x1280","360"),("wide","1600x1000","160")):
            adb("shell","wm","size",size)
            adb("shell","wm","density",density)
            adb("shell","am","force-stop","com.eftcalculator")
            adb("shell","am","start","-W","-n","com.eftcalculator/.MainActivity")
            time.sleep(2)
            pid = adb("shell","pidof","com.eftcalculator").decode().strip()
            adb("shell","uiautomator","dump","/sdcard/eft-audit.xml")
            xml = adb("shell","cat","/sdcard/eft-audit.xml")
            tree = ET.fromstring(xml)
            texts = [node.attrib.get("text","") for node in tree.iter("node")]
            assert "EFT Calculator" in texts
            key = f"{locale}-{name}"
            (out/f"{key}.xml").write_bytes(xml)
            (out/f"{key}.png").write_bytes(adb("exec-out","screencap","-p"))
            receipts.append({"locale":locale,"layout":name,"physical_size":size,"density":density,"pid":pid,"text_count":len(texts),"screenshot":f"{key}.png"})
    adb("shell","wm","size","reset")
    adb("shell","wm","density","reset")
    (out/"logcat.txt").write_bytes(adb("logcat","-d","-t","1200"))
    (out/"results.json").write_text(json.dumps({"serial":args.serial,"night":args.night,"apk_sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),"screenshots":receipts},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipts))


if __name__ == "__main__":
    main()
