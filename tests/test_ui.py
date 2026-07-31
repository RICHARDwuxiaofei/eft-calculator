from dataclasses import asdict, replace

import pytest

pytest.importorskip("PySide6")

from tarkov_armor_sim.data import SEED_AMMO, Database
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
    assert window.penetration_metric.text() == "请选择护甲"


def test_live_suggestion_manual_ammo_and_plate_autofill(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "ui-presets.sqlite3"))
    qtbot.addWidget(window)

    window.global_search.setText("855")
    labels = window.completion_model.stringList()
    assert labels[0].startswith("M855 ·")
    assert any(label.startswith("M855A1 ·") for label in labels)

    window._select_ammo_by_id("m855")
    window.custom_ammo_damage.setValue(99)
    window.custom_ammo_penetration.setValue(77)
    window._apply_custom_ammo()
    assert window.selected_ammo.source_version == "manual-override"
    assert window.selected_ammo.damage == 99
    assert window.selected_ammo.penetration_power == 77

    bagariy_index = window.carrier_combo.findData("bagariy")
    window.carrier_combo.setCurrentIndex(bagariy_index)
    assert window.plate_slot_combo.currentData() == "front"
    assert window.plate_combo.currentData() == "korund-front"
    assert window.manual_armor_class.value() == 5
    assert window.manual_max_durability.value() == 60
    window.manual_current_durability.setValue(33)
    window._confirm_armor_layer()
    assert window.layers[-1].name.startswith("Korund-VM")
    assert window.layers[-1].current_durability == 33


def test_window_uses_english_i18n_catalog(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EFT_CALCULATOR_LANG", "en_US")
    window = MainWindow(Database(tmp_path / "ui-en.sqlite3"))
    qtbot.addWidget(window)
    window.show()
    assert window.windowTitle() == "EFT Calculator · Layered Armor & Ballistics"
    assert window.penetration_metric.text() == "Choose armor"
    assert window.confirm_layer_button.text() == "Confirm and add as layer 1"


def test_tracker_caliber_filter_and_search_rows_use_item_icons(qtbot, tmp_path) -> None:
    database = Database(tmp_path / "online-ui.sqlite3")
    m855 = replace(
        SEED_AMMO[1],
        id="54527a984bdc2d4e668b4567",
        caliber="556x45",
    )
    m855a1 = replace(
        SEED_AMMO[0],
        id="54527ac44bdc2d36668b4567",
        caliber="556x45",
    )
    database.apply_ammo_snapshot(
        {
            "snapshot_id": "tracker-ui",
            "created_at": "2026-07-31T00:00:00+00:00",
            "ammo": [asdict(m855), asdict(m855a1)],
        }
    )
    window = MainWindow(database)
    qtbot.addWidget(window)

    window.caliber_group.button(1).click()
    assert window.ammo_list.count() == 2
    assert all(not window.ammo_list.item(row).icon().isNull() for row in range(2))
    assert window._ammo_icon(m855) != window._ammo_icon(m855a1)
    assert "5.56x45" in window.ammo_list.item(0).text()


def test_empty_results_offer_common_armor_shortcuts(qtbot, tmp_path) -> None:
    window = MainWindow(Database(tmp_path / "empty-state.sqlite3"))
    qtbot.addWidget(window)
    window._reset_armor()

    assert not window.empty_result_panel.isHidden()
    assert window.result_tabs.isHidden()
    choices = window.empty_result_panel.findChildren(type(window.selected_ammo_button))
    assert len(choices) >= 7
    choices[0].click()
    assert window.layers
    assert window.empty_result_panel.isHidden()
    assert not window.result_tabs.isHidden()
