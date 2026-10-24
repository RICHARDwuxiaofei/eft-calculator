import re

from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import create_application


def test_english_dynamic_controls_tables_and_chart_labels(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("EFT_CALCULATOR_LANG", "en_US")
    _, window = create_application(Database(tmp_path/"english.sqlite3"))
    qtbot.addWidget(window)
    window.shots.setValue(1)
    window._choose_preset(0)
    window._analyze()
    window._refresh_compare()
    texts = [widget.text() for kind in (QLabel, QAbstractButton) for widget in window.findChildren(kind)]
    texts += [widget.itemText(index) for widget in window.findChildren(QComboBox)
              for index in range(widget.count())]
    for table in (window.layer_table, window.layer_result_table, window.compare_table, window.burst_table):
        texts += [table.horizontalHeaderItem(index).text() for index in range(table.columnCount())]
    texts += [plot.getAxis(axis).labelText for plot in (window.plot, window.durability_plot, window.durability_sweep)
              for axis in ("left", "bottom")]
    assert not [text for text in texts if re.search(r"[\u4e00-\u9fff]", text)]
    window.close()
    window.thread_pool.waitForDone(10000)


def test_initial_wide_show_uses_actual_result_viewport_width(qtbot, tmp_path):
    _, window = create_application(Database(tmp_path/"first-show.sqlite3"))
    qtbot.addWidget(window)
    window.resize(1920, 1080)
    window.show()
    qtbot.wait(60)
    assert window.results_scroll.width() >= 800
    assert window.metric_grid.itemAtPosition(0, 2) is not None
    assert window.metric_grid.itemAtPosition(1, 2) is not None
    window.close()
    window.thread_pool.waitForDone(10000)
