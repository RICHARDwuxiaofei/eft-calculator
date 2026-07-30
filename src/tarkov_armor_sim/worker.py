from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .engine import simulate
from .models import ShotScenario, SimulationResult
from .rulesets import BallisticsRuleset


class WorkerSignals(QObject):
    progress = Signal(int)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class SimulationWorker(QRunnable):
    def __init__(self, scenario: ShotScenario, ruleset: BallisticsRuleset) -> None:
        super().__init__()
        self.scenario = scenario
        self.ruleset = ruleset
        self.signals = WorkerSignals()
        self.cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            result: SimulationResult = simulate(
                self.scenario,
                self.ruleset,
                progress=self.signals.progress.emit,
                cancelled=lambda: self.cancelled,
            )
            self.signals.result.emit(result)
        except Exception as exc:  # noqa: BLE001 - worker boundary converts failures to UI messages
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
