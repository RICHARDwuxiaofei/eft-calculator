import pytest

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.models import BodyPart
from tarkov_armor_sim.ui import MainWindow


@pytest.mark.parametrize('width,height',[(1440,1000),(800,900),(390,844),(360,640)])
def test_window_really_resizes_and_inputs_fit(qtbot,tmp_path,width,height):
    w=MainWindow(Database(tmp_path/'ui.db'));qtbot.addWidget(w);w.show();w.resize(width,height)
    qtbot.wait(50)
    assert w.width()==width
    assert w.height()==height
    assert w.input_panel.minimumSizeHint().width()<=width


def test_edit_replaces_instead_of_appending_and_repair_slider_uses_original(qtbot,tmp_path):
    w=MainWindow(Database(tmp_path/'ui.db'));qtbot.addWidget(w)
    w._choose_preset(0);w.layer_table.selectRow(0);count=len(w.layers)
    w._edit_layer();w.manual_max_durability.setValue(100);w.manual_repaired_durability.setValue(50);w.manual_current_durability.setValue(30)
    w._confirm_armor_layer()
    assert len(w.layers)==count
    assert w.layers[0].true_durability_ratio==.3
    assert w.durability_slider.maximum()==500
    w.durability_slider.setValue(500)
    assert w.layers[0].current_durability==50
    w.armor_dialog.hide()


def test_stomach_result_renders_without_fake_death_or_index_error(qtbot,tmp_path):
    w=MainWindow(Database(tmp_path/'ui.db'));qtbot.addWidget(w)
    w._choose_preset(0);w.shots.setValue(1)
    w.body_part.setCurrentIndex(w.body_part.findData(BodyPart.STOMACH))
    w._analyze()
    assert w.current_result.kill_probability_by_shot==[]
    assert w.burst_table.rowCount()==1


def test_changed_input_invalidates_exportable_old_result(qtbot,tmp_path):
    w=MainWindow(Database(tmp_path/'ui.db'));qtbot.addWidget(w)
    w._choose_preset(0);w.shots.setValue(1);w._analyze()
    assert w.current_result is not None
    w._schedule_analysis()
    assert w.current_result is None
    assert w.current_scenario is None
