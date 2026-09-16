"""Capture actual Qt layouts at desktop and phone-like widths for CI evidence."""
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('EFT_CALCULATOR_LANG','zh_CN')
from PySide6.QtWidgets import QApplication

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import MainWindow


def main():
    app=QApplication.instance() or QApplication([])
    target=Path('artifacts/ui');target.mkdir(parents=True,exist_ok=True)
    evidence=[]
    with tempfile.TemporaryDirectory() as tmp:
        window=MainWindow(Database(Path(tmp)/'ui.db'))
        window.shots.setValue(1);window._choose_preset(0);window._analyze();window.show()
        for width,height in ((1440,1000),(800,900),(390,844),(360,640)):
            window.resize(width,height)
            for _ in range(8):
                app.processEvents();time.sleep(.03)
            assert window.width()==width and window.height()==height
            assert window.input_panel.minimumSizeHint().width()<=width
            assert window.grab().save(str(target/f'layout-{width}.png'))
            evidence.append({'width':width,'height':height,'input_minimum_width':window.input_panel.minimumSizeHint().width()})
        window._open_armor_editor()
        for _ in range(8):
            app.processEvents();time.sleep(.03)
        assert window.armor_dialog.grab().save(str(target/'armor-editor.png'))
        window.armor_dialog.hide();window.close();app.processEvents()
    (target/'layout-checks.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':
    main()
