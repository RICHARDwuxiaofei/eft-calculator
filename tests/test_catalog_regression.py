import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from tarkov_armor_sim.data import ARMOR_PLATES, BUNDLED_CATALOG, SEED_AMMO, Database
from tarkov_armor_sim.ui_v2 import resource_path


@pytest.mark.parametrize('short,damage,pen,armor,speed', [
    ('DBX95',57,33,40,910),('DBP191',53,39,43,840),
    ('DVX12',48,47,54,850),('DVC12',46,52,60,872),
])
def test_wiki_58_facts(short,damage,pen,armor,speed):
    item = next(x for x in BUNDLED_CATALOG['ammo'] if x['caliber']=='5.8x42' and x['short_name']==short)
    assert (item['damage'],item['penetration_power'],item['armor_damage_percent'],item['muzzle_velocity'],item['projectile_count']) == (damage,pen,armor,speed,1)


def test_each_catalog_item_has_its_own_verified_image_bytes():
    manifest=json.loads(resource_path('items','image-manifest.json').read_text())
    assert len(BUNDLED_CATALOG['ammo']) == 184
    assert len(ARMOR_PLATES) == 38
    assert len(manifest['items']) == 222
    for item_id,record in manifest['items'].items():
        assert Path(record['path']).stem == item_id
        image=resource_path('items',*record['path'].split('/'))
        assert hashlib.sha256(image.read_bytes()).hexdigest()==record['sha256']
        assert image.read_bytes().startswith((b'RIFF',b'\x89PNG'))


def test_snapshot_merge_preserves_58_and_user_favorites(tmp_path):
    db=Database(tmp_path/'test.db')
    db.set_favorite('m855a1',True)
    record=replace(SEED_AMMO[0],id='54527ac44bdc2d36668b4567',damage=48,source_version='manual-test')
    db.apply_ammo_snapshot({'snapshot_id':'test','created_at':'2026-09-16T00:00:00Z','ammo':[asdict(record)]})
    assert len(db.search_ammo('', '5.8x42'))==4
    assert db.is_favorite(record.id)
    db.connection.close()
    reopened=Database(tmp_path/'test.db')
    assert next(x for x in reopened.all_ammo() if x.id==record.id).damage==48


def test_invalid_snapshot_is_atomic(tmp_path):
    db=Database(tmp_path/'test.db'); before=db.all_ammo()
    bad=asdict(SEED_AMMO[0]);bad['damage']=float('nan')
    with pytest.raises(ValueError):
        db.apply_ammo_snapshot({'snapshot_id':'bad','created_at':'2026-09-16','ammo':[bad]})
    assert db.all_ammo()==before


def test_historical_fallback_cannot_replace_verified_data(tmp_path):
    db=Database(tmp_path/'test.db')
    with pytest.raises(ValueError):
        db.apply_ammo_snapshot({'snapshot_id':'old','created_at':'2026-09-16','sources':[{'source':'TarkovTracker/tarkovdata'}],'ammo':[asdict(SEED_AMMO[0])]})


def test_upgrade_replaces_old_live_snapshot_but_preserves_manual_override(tmp_path):
    db=Database(tmp_path/'upgrade.db')
    original=next(x for x in db.all_ammo() if x.id=='54527ac44bdc2d36668b4567')
    old=replace(original,damage=47,source_version='tarkov.dev-2026-07-31')
    with db.connection:
        db._upsert_ammo(old)
        db.connection.execute("DELETE FROM metadata WHERE key='bundled_catalog_version'")
    db.connection.close()
    db=Database(tmp_path/'upgrade.db')
    assert next(x for x in db.all_ammo() if x.id==original.id).damage==49
    with db.connection:
        db._upsert_ammo(replace(old,damage=88,source_version='manual-override'))
        db.connection.execute("DELETE FROM metadata WHERE key='bundled_catalog_version'")
    db.connection.close()
    db=Database(tmp_path/'upgrade.db')
    assert next(x for x in db.all_ammo() if x.id==original.id).damage==88
