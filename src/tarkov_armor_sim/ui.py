"""Compatibility entry point for the redesigned two-region desktop interface.

This module also applies presentation-level chart guards.  The simulation returns
probabilities as fractions in [0, 1]; probability plots are therefore never allowed
to pan or auto-range outside 0..100 percent, and x ranges are reset to the actual
data horizon after every recalculation.
"""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from . import ui_v2 as _base
from .data import Database

resource_path = _base.resource_path


def _percent(value: float) -> float:
    """Convert a probability fraction to a display percentage defensively."""
    return max(0.0, min(100.0, float(value) * 100.0))


def _lock_view(
    plot: pg.PlotWidget,
    *,
    x_min: float,
    x_max: float,
    y_min: float | None = None,
    y_max: float | None = None,
) -> None:
    """Reset stale zoom/pan state and prevent physically meaningless ranges."""
    if x_max <= x_min:
        x_max = x_min + 1.0
    limits: dict[str, float] = {"xMin": x_min, "xMax": x_max}
    if y_min is not None:
        limits["yMin"] = y_min
    if y_max is not None:
        limits["yMax"] = y_max
    plot.getViewBox().setLimits(**limits)
    plot.setXRange(x_min, x_max, padding=0)
    if y_min is not None and y_max is not None:
        plot.setYRange(y_min, y_max, padding=0)


class MainWindow(_base.MainWindow):
    """Desktop window with bounded, data-sized chart viewports."""

    def _plot_result(self, result) -> None:
        super()._plot_result(result)

        probabilities = list(result.penetration_probability_by_shot)
        if probabilities:
            # Replot with defensive clipping so even a future upstream regression
            # cannot draw impossible percentages outside the physical domain.
            shots = list(range(1, len(probabilities) + 1))
            self.plot.clear()
            self.plot.plot(
                shots,
                [_percent(value) for value in probabilities],
                pen=pg.mkPen("#efc36a", width=2),
                symbol="o",
            )
            _lock_view(
                self.plot,
                x_min=0.5,
                x_max=len(shots) + 0.5,
                y_min=0.0,
                y_max=100.0,
            )

        timeline = list(result.durability_timeline)
        if timeline:
            final_shot = max(snapshot.shot for snapshot in timeline)
            durability_values = [
                value for snapshot in timeline for value in snapshot.durability
            ]
            highest = max(durability_values, default=0.0)
            _lock_view(
                self.durability_plot,
                x_min=0.0,
                x_max=max(1.0, float(final_shot)),
                y_min=0.0,
                y_max=max(1.0, highest * 1.05),
            )

        scenario = self.current_scenario
        if scenario is not None and scenario.armor_layers:
            row = self.layer_table.currentRow()
            if not 0 <= row < len(scenario.armor_layers):
                row = 0
            maximum = max(1.0, scenario.armor_layers[row].displayed_max_durability)
            _lock_view(
                self.durability_sweep,
                x_min=0.0,
                x_max=maximum,
                y_min=0.0,
                y_max=100.0,
            )


def create_application(database: Database) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("EFT Calculator")
    app.setOrganizationName("EFTCalculator")
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setWindowIcon(QIcon(str(resource_path("icons", "app-icon.png"))))
    return app, MainWindow(database)


__all__ = ["MainWindow", "create_application", "resource_path"]
