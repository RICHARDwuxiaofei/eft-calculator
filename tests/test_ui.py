import pytest

pytest.importorskip("PySide6")

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import MainWindow


@pytest.fixture(autouse=True)
def _default_ui_locale(monkeypatch) -> None:
    monkeypatch.setenv("EFT_CALCULATOR_LANG", "zh_CN")


def test_main_window_starts_and_is_not_empty(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui.sqlite3"))
    qtbot.addWidget(window)
    window.show()
    assert window.ammo_list.count() > 0
    assert window.layer_table.rowCount() == 0
    assert "第 1 层" in window.confirm_layer_button.text()
    assert window.penetration_metric.text() != ""


def test_search_and_slider_refresh(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui.sqlite3"))
    qtbot.addWidget(window)
    window.global_search.setText("M855A1")
    assert window.ammo_list.count() == 1
    window._choose_preset(0)
    old = window.layers[0].current_durability
    window.durability_slider.setValue(max(0, window.durability_slider.value() - 50))
    assert window.layers[0].current_durability < old


def test_add_and_remove_layer(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui.sqlite3"))
    qtbot.addWidget(window)
    count = len(window.layers)
    window._add_layer()
    assert len(window.layers) == count + 1
    window.layer_table.selectRow(len(window.layers) - 1)
    window._remove_layer()
    assert len(window.layers) == count


def test_large_button_ammo_and_layer_builder(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui.sqlite3"))
    qtbot.addWidget(window)

    window.caliber_group.button(1).click()
    assert window.caliber_filter.currentData() == "5.56x45"
    assert window.ammo_choice_group.buttons()
    window.ammo_choice_group.buttons()[0].click()
    assert not window.ammo_choice_group.buttons()[0].icon().isNull()
    assert window.selected_ammo is not None
    assert window.selected_ammo.caliber == "5.56x45"

    window._reset_armor()
    assert window.layers == []
    window.armor_class_group.button(5).click()
    window.material_group.button(1).click()
    assert not window.material_group.button(1).icon().isNull()
    window._confirm_armor_layer()
    assert len(window.layers) == 1
    assert window.layers[0].armor_class == 5
    assert window.layers[0].material.value == "ceramic"
    window.armor_class_group.button(3).click()
    window.material_group.button(4).click()
    window._confirm_armor_layer()
    assert len(window.layers) == 2
    assert window.layers[1].armor_class == 3
    assert window.layers[1].material.value == "aramid"


def test_separate_resets(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui.sqlite3"))
    qtbot.addWidget(window)
    window.global_search.setText("BP")
    window._reset_ammo()
    assert window.selected_ammo is not None
    assert window.selected_ammo.id == "m855a1"
    window._reset_armor()
    assert len(window.layers) == 0
    assert "请添加护甲" in window.penetration_metric.text()


def test_window_uses_english_i18n_catalog(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EFT_CALCULATOR_LANG", "en_US")
    window = MainWindow(Database(tmp_path / "ui-en.sqlite3"))
    qtbot.addWidget(window)
    window.show()
    assert window.windowTitle() == "EFT Calculator · Layered Armor & Ballistics"
    assert "Add armor" in window.penetration_metric.text()
    assert window.confirm_layer_button.text() == "Confirm and add as layer 1"
