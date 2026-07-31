from __future__ import annotations

from tarkov_armor_sim.i18n import SUPPORTED_LOCALES, I18n


def test_supported_locales_and_english_catalog() -> None:
    assert SUPPORTED_LOCALES == ("zh_CN", "en_US")
    english = I18n("en_US")
    assert english.translate("弹药") == "Ammo"
    assert (
        english.translate("确认并添加为第 {layer} 层", layer=2)
        == "Confirm and add as layer 2"
    )


def test_catalog_can_switch_back_to_chinese() -> None:
    translator = I18n("en_US")
    assert translator.translate("设置") == "Settings"
    translator.set_locale("zh_CN")
    assert translator.translate("Settings") == "设置"
