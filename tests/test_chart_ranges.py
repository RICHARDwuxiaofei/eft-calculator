from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.engine import analyze
from tarkov_armor_sim.ui import MainWindow


def test_result_charts_reset_stale_zoom_and_stay_physical(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "chart-ranges.sqlite3"))
    qtbot.addWidget(window)
    window._choose_preset(0)
    window._analysis_timer.stop()
    window.shots.setValue(16)
    window._analysis_timer.stop()

    scenario = window._scenario(iterations=256)
    result = analyze(scenario, window.ruleset)
    window.current_scenario = scenario

    # Reproduce the screenshot failure: stale/manual view ranges far outside data.
    window.plot.setRange(xRange=(-100, 100), yRange=(-200, 250), padding=0)
    window.durability_plot.setRange(xRange=(-100, 100), yRange=(-100, 250), padding=0)
    window.durability_sweep.setRange(xRange=(-100, 200), yRange=(-200, 300), padding=0)

    window._plot_result(result)

    probability_x, probability_y = window.plot.viewRange()
    assert probability_x == pytest.approx([0.5, 16.5])
    assert probability_y == pytest.approx([0.0, 100.0])

    plotted_probability = window.plot.listDataItems()[0].getData()[1]
    assert plotted_probability is not None
    assert all(0.0 <= float(value) <= 100.0 for value in plotted_probability)

    durability_x, durability_y = window.durability_plot.viewRange()
    assert durability_x == pytest.approx([0.0, 16.0])
    assert durability_y[0] == pytest.approx(0.0)
    assert durability_y[1] > 0.0

    sweep_x, sweep_y = window.durability_sweep.viewRange()
    assert sweep_x[0] == pytest.approx(0.0)
    assert sweep_x[1] == pytest.approx(scenario.armor_layers[0].displayed_max_durability)
    assert sweep_y == pytest.approx([0.0, 100.0])


def test_probability_display_clips_impossible_upstream_values() -> None:
    from tarkov_armor_sim.ui import _percent

    assert _percent(-2.0) == 0.0
    assert _percent(0.42) == 42.0
    assert _percent(3.0) == 100.0
