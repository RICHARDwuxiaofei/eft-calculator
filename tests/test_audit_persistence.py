import json
from dataclasses import asdict

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import MainWindow


def test_physical_database_corruption_preserves_original_bytes(tmp_path):
    path = tmp_path/"corrupt.sqlite3"
    content = b"not a sqlite database\x00original-user-data"
    path.write_bytes(content)
    db = Database(path)
    assert db.recovery_backup.read_bytes() == content
    assert len(db.all_ammo()) >= 184
    db.connection.close()


def test_bad_row_is_quarantined_without_losing_favorites(tmp_path):
    path = tmp_path/"bad-row.sqlite3"
    db = Database(path)
    item = db.all_ammo()[0]
    db.set_favorite(item.id, True)
    damaged = asdict(item)
    damaged["damage"] = "invalid-user-value"
    encoded = json.dumps(damaged)
    with db.connection:
        db.connection.execute("UPDATE ammo SET payload=? WHERE id=?", (encoded,item.id))
    db.connection.close()
    db = Database(path)
    assert db.is_favorite(item.id)
    assert next(x for x in db.all_ammo() if x.id == item.id).damage == item.damage
    recovered = db.connection.execute("SELECT original_payload FROM quarantined_ammo WHERE item_id=?", (item.id,)).fetchone()
    assert recovered[0] == encoded
    assert path.with_name(path.name+".before-row-repair.bak").exists()
    db.connection.close()


def test_desktop_session_restores_layers_conditions_and_custom_values(qtbot,tmp_path):
    db = Database(tmp_path/"session.sqlite3")
    w = MainWindow(db)
    qtbot.addWidget(w)
    w._choose_preset(0)
    w.layers[0].current_durability = 12
    w.layers[0].displayed_max_durability = 30
    w.shots.setValue(7)
    w.distance.setValue(125)
    w.distance_decay.setChecked(True)
    w._save_session()
    w.close()
    w.thread_pool.waitForDone(10000)
    second = MainWindow(db)
    qtbot.addWidget(second)
    assert second.shots.value() == 7
    assert second.distance.value() == 125
    assert second.distance_decay.isChecked()
    assert len(second.layers) == 2
    assert second.layers[0].current_durability == 12
    assert second.layers[0].displayed_max_durability == 30
    second.close()
    second.thread_pool.waitForDone(10000)
