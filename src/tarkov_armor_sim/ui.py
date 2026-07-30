from __future__ import annotations

import logging
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .data import DATA_VERSION, Database, default_armor_presets
from .models import Ammo, ArmorLayer, ArmorLayerType, ArmorMaterial, BodyPart, ShotScenario
from .rulesets import CurrentApproximation, ExperimentalRuleset
from .services import export_csv, export_json, result_summary
from .worker import SimulationWorker

LOGGER = logging.getLogger(__name__)

STYLE = """
QWidget { background: #13171b; color: #e8ebee; font-size: 14px; }
QMainWindow { background: #0e1114; }
QFrame#card { background: #1b2025; border: 1px solid #303840; border-radius: 10px; }
QFrame#hero { background: #212830; border: 1px solid #bd9958; border-radius: 12px; }
QFrame#metricCard { background: #161b20; border: 1px solid #303840; border-radius: 7px; }
QLineEdit, QComboBox, QSpinBox, QListWidget, QTableWidget {
  background: #0f1317; border: 1px solid #3b454f; border-radius: 6px; padding: 7px;
}
QPushButton { background: #2a323a; border: 1px solid #46515c; border-radius: 6px; padding: 8px 12px; }
QPushButton:hover { background: #424b56; }
QPushButton#primary { background: #c3a05e; color: #0c0f11; font-weight: 800; }
QPushButton#choice { text-align: left; padding: 11px 13px; min-height: 32px; }
QPushButton#choice:checked { background: #b99554; color: #101316; border-color: #e4bf78; font-weight: 800; }
QPushButton#caliber { padding: 11px; min-height: 32px; font-weight: 700; }
QPushButton#caliber:checked { background: #b99554; color: #101316; border-color: #e4bf78; }
QLabel#metric { font-size: 42px; font-weight: 900; color: #f0c66f; }
QLabel#metricValue { font-size: 21px; font-weight: 800; color: #f1f3f5; }
QLabel#muted { color: #9ca6af; }
QLabel#section { font-size: 18px; font-weight: 800; color: #f5f6f7; }
QLabel#step { color: #d0a95f; font-size: 12px; font-weight: 800; }
QProgressBar { border: 1px solid #3b424c; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background: #b89655; }
QTabBar::tab { padding: 8px 16px; background: #20242a; }
QTabBar::tab:selected { background: #343b44; color: #eac879; }
"""


class MainWindow(QMainWindow):
    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.settings = QSettings("OpenAI", "TarkovArmorSimulator")
        self.ruleset = CurrentApproximation()
        self.ammo_items: list[Ammo] = []
        self.selected_ammo: Ammo | None = None
        self.layers: list[ArmorLayer] = []
        self.current_result = None
        self.current_scenario: ShotScenario | None = None
        self.worker: SimulationWorker | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle("Escape from Tarkov 护甲模拟器 — 非官方")
        self.resize(1440, 900)
        self.setMinimumSize(980, 650)
        self._build_ui()
        self._build_shortcuts()
        self._restore_settings()
        self._refresh_ammo()
        self._reset_all()

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 8, 10, 8)

        top = QHBoxLayout()
        step = QLabel("第 1 步  搜弹药")
        step.setObjectName("step")
        top.addWidget(step)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("输入 M855A1、855a1、5.56、BP 或 7N40")
        self.global_search.textChanged.connect(self._refresh_ammo)
        self.mode_button = QPushButton("快速模式")
        self.mode_button.clicked.connect(self._toggle_lab)
        self.compact_button = QPushButton("紧凑模式")
        self.compact_button.clicked.connect(self._toggle_compact)
        self.pin_button = QPushButton("置顶：关")
        self.pin_button.clicked.connect(self._toggle_pin)
        reset_all = QPushButton("重置全部")
        reset_all.clicked.connect(self._reset_all)
        top.addWidget(self.global_search, 1)
        top.addWidget(self.mode_button)
        top.addWidget(self.compact_button)
        top.addWidget(self.pin_button)
        top.addWidget(reset_all)
        version = QLabel(f"离线可用 · {DATA_VERSION}")
        version.setObjectName("muted")
        top.addWidget(version)
        outer.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_simulator(), "模拟器")
        self.tabs.addTab(self._build_compare(), "对比")
        self.tabs.addTab(self._build_about(), "公式与来源")
        outer.addWidget(self.tabs, 1)

        self.status = QLabel("就绪")
        outer.addWidget(self.status)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("section")
        layout.addWidget(label)
        return card, layout

    def _build_simulator(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        ammo_scroll = QScrollArea()
        ammo_scroll.setWidgetResizable(True)
        ammo_scroll.setFrameShape(QFrame.Shape.NoFrame)
        ammo_scroll.setWidget(self._build_ammo_panel())
        ammo_scroll.setMinimumWidth(310)
        self.input_panel = ammo_scroll
        armor_scroll = QScrollArea()
        armor_scroll.setWidgetResizable(True)
        armor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        armor_scroll.setWidget(self._build_armor_panel())
        armor_scroll.setMinimumWidth(390)
        self.splitter.addWidget(ammo_scroll)
        self.splitter.addWidget(armor_scroll)
        self.splitter.addWidget(self._build_results_panel())
        self.splitter.setSizes([330, 440, 670])
        layout.addWidget(self.splitter)
        return page

    def _build_ammo_panel(self) -> QWidget:
        panel, layout = self._card("① 选择弹药")

        layout.addWidget(QLabel("先选口径"))
        self.caliber_filter = QComboBox()
        self.caliber_filter.addItem("全部口径", "")
        for caliber in ("5.56x45", "5.45x39", "7.62x39", "7.62x51", "12/70"):
            self.caliber_filter.addItem(caliber, caliber)
        self.caliber_filter.currentIndexChanged.connect(self._refresh_ammo)
        self.caliber_filter.hide()

        self.caliber_group = QButtonGroup(self)
        self.caliber_group.setExclusive(True)
        caliber_grid = QGridLayout()
        caliber_grid.setSpacing(6)
        for index in range(self.caliber_filter.count()):
            text = self.caliber_filter.itemText(index)
            button = QPushButton(text)
            button.setObjectName("caliber")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, current=index: self.caliber_filter.setCurrentIndex(current)
            )
            self.caliber_group.addButton(button, index)
            caliber_grid.addWidget(button, index // 3, index % 3)
        self.caliber_group.button(0).setChecked(True)
        layout.addLayout(caliber_grid)

        layout.addWidget(QLabel("再选弹药"))
        self.ammo_button_host = QWidget()
        self.ammo_button_grid = QGridLayout(self.ammo_button_host)
        self.ammo_button_grid.setContentsMargins(0, 0, 0, 0)
        self.ammo_button_grid.setSpacing(6)
        layout.addWidget(self.ammo_button_host)

        # Kept as an internal keyboard/search model; the visible UI uses large buttons.
        self.ammo_list = QListWidget()
        self.ammo_list.currentRowChanged.connect(self._select_ammo)
        self.ammo_list.hide()
        self.ammo_card = QLabel("请选择弹药")
        self.ammo_card.setWordWrap(True)
        self.ammo_card.setMaximumHeight(95)
        layout.addWidget(self.ammo_card)

        ammo_actions = QHBoxLayout()
        self.favorite_button = QPushButton("☆ 收藏")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        reset_ammo = QPushButton("重置弹药")
        reset_ammo.clicked.connect(self._reset_ammo)
        ammo_actions.addWidget(self.favorite_button)
        ammo_actions.addWidget(reset_ammo)
        layout.addLayout(ammo_actions)
        self.manual_ammo_button = QPushButton("手动弹药…")
        self.manual_ammo_button.clicked.connect(self._manual_ammo)
        self.manual_ammo_button.hide()
        layout.addWidget(self.manual_ammo_button)
        return panel

    def _build_armor_panel(self) -> QWidget:
        panel, layout = self._card("② 一键组成护甲层")
        layout.addWidget(QLabel("常用组合预设"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(default_armor_presets().keys())
        self.preset_combo.currentIndexChanged.connect(self._load_preset)
        self.preset_combo.hide()
        preset_grid = QGridLayout()
        for index, preset_name in enumerate(default_armor_presets()):
            button = QPushButton(preset_name)
            button.setObjectName("choice")
            button.clicked.connect(
                lambda _checked=False, current=index: self._choose_preset(current)
            )
            preset_grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(preset_grid)

        layout.addWidget(QLabel("或逐层添加"))
        type_row = QHBoxLayout()
        self.armor_type_group = QButtonGroup(self)
        self.armor_type_group.setExclusive(True)
        for index, (title, value) in enumerate(
            (
                ("硬插板", ArmorLayerType.PLATE),
                ("软甲", ArmorLayerType.SOFT),
                ("头盔", ArmorLayerType.HELMET),
            )
        ):
            button = QPushButton(title)
            button.setObjectName("caliber")
            button.setCheckable(True)
            button.setProperty("armor_type", value)
            self.armor_type_group.addButton(button, index)
            type_row.addWidget(button)
        self.armor_type_group.button(0).setChecked(True)
        layout.addLayout(type_row)

        chooser = QGridLayout()
        chooser.addWidget(QLabel("等级"), 0, 0)
        chooser.addWidget(QLabel("材质"), 0, 1)
        self.armor_class_group = QButtonGroup(self)
        self.armor_class_group.setExclusive(True)
        for armor_class in range(1, 7):
            button = QPushButton(f"{armor_class} 级")
            button.setObjectName("choice")
            button.setCheckable(True)
            button.setProperty("armor_class", armor_class)
            self.armor_class_group.addButton(button, armor_class)
            chooser.addWidget(button, armor_class, 0)
        self.armor_class_group.button(5).setChecked(True)

        self.material_group = QButtonGroup(self)
        self.material_group.setExclusive(True)
        material_options = (
            ("陶瓷", ArmorMaterial.CERAMIC),
            ("钢", ArmorMaterial.STEEL),
            ("UHMWPE", ArmorMaterial.UHMWPE),
            ("芳纶", ArmorMaterial.ARAMID),
            ("钛", ArmorMaterial.TITANIUM),
            ("复合", ArmorMaterial.COMBINED),
        )
        for row, (title, value) in enumerate(material_options, 1):
            button = QPushButton(title)
            button.setObjectName("choice")
            button.setCheckable(True)
            button.setProperty("material", value)
            self.material_group.addButton(button, row)
            chooser.addWidget(button, row, 1)
        self.material_group.button(1).setChecked(True)
        layout.addLayout(chooser)

        self.confirm_layer_button = QPushButton("确认并添加为第 1 层")
        self.confirm_layer_button.setObjectName("primary")
        self.confirm_layer_button.clicked.connect(self._confirm_armor_layer)
        layout.addWidget(self.confirm_layer_button)

        self.layer_actions = QWidget()
        actions = QHBoxLayout(self.layer_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        add = QPushButton("＋ 添加层")
        add.clicked.connect(self._add_layer)
        edit = QPushButton("编辑层…")
        edit.clicked.connect(self._edit_layer)
        remove = QPushButton("－ 删除层")
        remove.clicked.connect(self._remove_layer)
        save = QPushButton("保存预设")
        save.clicked.connect(self._save_preset)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addWidget(save)
        self.layer_actions.hide()
        layout.addWidget(self.layer_actions)

        self.layer_table = QTableWidget(0, 6)
        self.layer_table.setHorizontalHeaderLabels(
            ["层", "名称", "等级", "材料", "当前/出厂", "真实比例"]
        )
        self.layer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layer_table.currentCellChanged.connect(self._layer_selection_changed)
        self.layer_table.verticalHeader().hide()
        self.layer_table.setMaximumHeight(145)
        layout.addWidget(self.layer_table)

        self.durability_label = QLabel("当前耐久")
        self.durability_slider = QSlider(Qt.Orientation.Horizontal)
        self.durability_slider.valueChanged.connect(self._durability_changed)
        layout.addWidget(self.durability_label)
        layout.addWidget(self.durability_slider)

        reset_armor = QPushButton("重置护甲")
        reset_armor.clicked.connect(self._reset_armor)
        layout.addWidget(reset_armor)

        form = QFormLayout()
        self.distance = QSpinBox()
        self.distance.setRange(0, 1000)
        self.distance.setSuffix(" m")
        self.distance.valueChanged.connect(self._schedule_analysis)
        self.shots = QSpinBox()
        self.shots.setRange(1, 100)
        self.shots.setValue(3)
        self.shots.valueChanged.connect(self._schedule_analysis)
        self.iterations = QComboBox()
        self.iterations.addItem("快速 1,000", 1000)
        self.iterations.addItem("标准 10,000", 10000)
        self.iterations.addItem("高精度 100,000", 100000)
        self.ruleset_combo = QComboBox()
        self.ruleset_combo.addItem("当前社区近似", "current")
        self.ruleset_combo.addItem("实验性距离强化", "experimental")
        self.ruleset_combo.currentIndexChanged.connect(self._ruleset_changed)
        form.addRow("距离", self.distance)
        form.addRow("连续射击", self.shots)
        form.addRow("蒙特卡洛", self.iterations)
        self.lab_ruleset_row = QWidget()
        lab_layout = QHBoxLayout(self.lab_ruleset_row)
        lab_layout.setContentsMargins(0, 0, 0, 0)
        lab_layout.addWidget(self.ruleset_combo)
        form.addRow("规则集", self.lab_ruleset_row)
        self.iterations_label = form.labelForField(self.iterations)
        self.iterations.hide()
        self.iterations_label.hide()
        self.lab_ruleset_row.hide()
        layout.addLayout(form)
        self.simulate_button = QPushButton("运行蒙特卡洛")
        self.simulate_button.setObjectName("primary")
        self.simulate_button.clicked.connect(self._run_simulation)
        self.simulate_button.hide()
        layout.addWidget(self.simulate_button)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel, layout = self._card("③ 直接看结论")

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_label = QLabel("首发穿过全部护甲并到达人体")
        hero_label.setObjectName("muted")
        self.penetration_metric = QLabel("—")
        self.penetration_metric.setObjectName("metric")
        self.conclusion = QLabel("选择弹药和护甲后自动计算，无需点击按钮。")
        self.conclusion.setWordWrap(True)
        hero_layout.addWidget(hero_label)
        hero_layout.addWidget(self.penetration_metric)
        hero_layout.addWidget(self.conclusion)
        layout.addWidget(hero)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.result_values: dict[str, QLabel] = {}
        metric_specs = (
            ("three", "3 发内至少穿透一次"),
            ("first", "预计首次穿透"),
            ("health", "首发期望肉伤"),
            ("blunt", "首发期望钝伤"),
            ("kill", "连续射击致死概率"),
            ("confidence", "规则可信度"),
        )
        for index, (key, title) in enumerate(metric_specs):
            tile = QFrame()
            tile.setObjectName("metricCard")
            tile_layout = QVBoxLayout(tile)
            caption = QLabel(title)
            caption.setObjectName("muted")
            value = QLabel("—")
            value.setObjectName("metricValue")
            tile_layout.addWidget(caption)
            tile_layout.addWidget(value)
            metrics.addWidget(tile, index // 3, index % 3)
            self.result_values[key] = value
        layout.addLayout(metrics)

        self.result_grid = QLabel("")
        self.result_grid.hide()

        result_tabs = QTabWidget()
        trend_page = QWidget()
        trend_layout = QVBoxLayout(trend_page)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#16191d")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "射击序号")
        self.plot.setLabel("left", "概率 / 耐久")
        self.plot.setMinimumHeight(270)
        trend_layout.addWidget(self.plot)
        result_tabs.addTab(trend_page, "连续射击趋势")

        self.layer_details = QLabel("")
        self.layer_details.setWordWrap(True)
        self.layer_details.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.layer_details)
        result_tabs.addTab(scroll, "逐层计算明细")
        layout.addWidget(result_tabs, 1)
        self.result_tabs = result_tabs

        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("详细结果和导出不是快速查询必需项"))
        export_row.addStretch()
        export_csv_button = QPushButton("导出 CSV")
        export_csv_button.clicked.connect(lambda: self._export("csv"))
        export_json_button = QPushButton("导出 JSON")
        export_json_button.clicked.connect(lambda: self._export("json"))
        export_row.addWidget(export_csv_button)
        export_row.addWidget(export_json_button)
        layout.addLayout(export_row)
        self.results_panel = panel
        return panel

    def _build_compare(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("对比当前离线弹药对同一护甲路径的解析结果；点击表头可排序。")
        layout.addWidget(note)
        run = QPushButton("刷新对比")
        run.clicked.connect(self._refresh_compare)
        layout.addWidget(run)
        self.compare_table = QTableWidget(0, 7)
        self.compare_table.setHorizontalHeaderLabels(
            ["弹药", "口径", "首发穿透率", "3发内", "期望首穿发数", "期望肉伤", "期望钝伤"]
        )
        self.compare_table.setSortingEnabled(True)
        layout.addWidget(self.compare_table)
        return page

    def _build_about(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(
            "<h2>规则透明度</h2>"
            "<p>默认规则：community-approx-2026.07-v1（社区近似）</p>"
            "<p>游戏版本参考：1.0.6.0；数据快照：2026-07-30。</p>"
            "<p>穿透概率使用穿深、护甲等级和相对出厂耐久的单调 Logistic 近似；"
            "耐久损伤、穿透后衰减、钝伤和距离衰减均非官方公开精确公式。</p>"
            "<p>来源：<a href='https://tarkov.dev/api/'>tarkov.dev API</a> · "
            "<a href='https://escapefromtarkov.fandom.com/wiki/Ballistics'>Ballistics Wiki</a> · "
            "<a href='https://changes.tarkov-changes.com/'>Tarkov Changes</a></p>"
            "<p>本工具不读取游戏内存、不注入进程、不绕过反作弊。</p>"
        )
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_shortcuts(self) -> None:
        mapping = {
            "Ctrl+K": self.global_search.setFocus,
            "Ctrl+1": self.global_search.setFocus,
            "Ctrl+2": self.preset_combo.setFocus,
            "Ctrl+3": self._focus_results,
            "Ctrl+D": self._toggle_favorite,
            "Ctrl+S": self._save_preset,
            "Ctrl+M": self._toggle_lab,
            "Ctrl+T": self._toggle_pin,
            "Escape": self.global_search.clear,
        }
        self.shortcuts = []
        for key, callback in mapping.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        compact_action = QAction("紧凑模式", self)
        compact_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        compact_action.triggered.connect(self._toggle_compact)
        self.addAction(compact_action)

    def _refresh_ammo(self, *_args) -> None:
        query = self.global_search.text() if hasattr(self, "global_search") else ""
        caliber = self.caliber_filter.currentData() if hasattr(self, "caliber_filter") else ""
        self.ammo_items = self.database.search_ammo(query, caliber)

        while self.ammo_button_grid.count():
            item = self.ammo_button_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.ammo_choice_group = QButtonGroup(self)
        self.ammo_choice_group.setExclusive(True)
        selected_id = self.selected_ammo.id if self.selected_ammo else None
        for index, ammo in enumerate(self.ammo_items[:8]):
            button = QPushButton(
                f"{ammo.short_name}\n伤害 {ammo.damage:g}  ·  穿深 {ammo.penetration_power:g}"
            )
            button.setObjectName("choice")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, current=index: self._select_ammo(current)
            )
            self.ammo_choice_group.addButton(button, index)
            self.ammo_button_grid.addWidget(button, index // 2, index % 2)
            if ammo.id == selected_id:
                button.setChecked(True)

        self.ammo_list.blockSignals(True)
        self.ammo_list.clear()
        for ammo in self.ammo_items:
            star = "★ " if self.database.is_favorite(ammo.id) else ""
            self.ammo_list.addItem(
                f"{star}{ammo.short_name:<10}  {ammo.caliber}  伤害 {ammo.damage:g}  穿深 {ammo.penetration_power:g}"
            )
        self.ammo_list.blockSignals(False)
        if self.ammo_items:
            selected_index = next(
                (
                    index
                    for index, ammo in enumerate(self.ammo_items)
                    if ammo.id == selected_id
                ),
                0,
            )
            self.ammo_list.setCurrentRow(selected_index)
            self._select_ammo(selected_index)
        self.status.setText(f"找到 {len(self.ammo_items)} 种弹药")

    def _select_ammo(self, row: int) -> None:
        if not 0 <= row < len(self.ammo_items):
            return
        self.selected_ammo = self.ammo_items[row]
        ammo = self.selected_ammo
        choice = self.ammo_choice_group.button(row) if hasattr(self, "ammo_choice_group") else None
        if choice:
            choice.setChecked(True)
        self.database.mark_recent(ammo.id)
        self.ammo_card.setText(
            f"<b>{ammo.name}</b><br>伤害：{ammo.damage:g}<br>穿深：{ammo.penetration_power:g}"
            f"<br>甲伤：{ammo.armor_damage_percent:g}%<br>弹丸：{ammo.projectile_count}"
            f"<br>初速：{ammo.muzzle_velocity or '未知'} m/s<br>数据：{ammo.source_version}"
        )
        self.favorite_button.setText(
            "★ 取消收藏" if self.database.is_favorite(ammo.id) else "☆ 收藏当前弹药"
        )
        self._schedule_analysis()

    def _toggle_favorite(self) -> None:
        if self.selected_ammo is None:
            return
        value = not self.database.is_favorite(self.selected_ammo.id)
        self.database.set_favorite(self.selected_ammo.id, value)
        self._refresh_ammo()

    def _manual_ammo(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("手动弹药")
        form = QFormLayout(dialog)
        name = QLineEdit("自定义弹药")
        caliber = QLineEdit("自定义")
        damage = QDoubleSpinBox()
        damage.setRange(0, 1000)
        damage.setValue(50)
        penetration = QDoubleSpinBox()
        penetration.setRange(0, 100)
        penetration.setValue(40)
        armor_damage = QDoubleSpinBox()
        armor_damage.setRange(0, 100)
        armor_damage.setValue(50)
        projectiles = QSpinBox()
        projectiles.setRange(1, 32)
        velocity = QDoubleSpinBox()
        velocity.setRange(0, 2000)
        velocity.setValue(800)
        form.addRow("名称", name)
        form.addRow("口径", caliber)
        form.addRow("肉伤", damage)
        form.addRow("穿深", penetration)
        form.addRow("甲伤 %", armor_damage)
        form.addRow("弹丸数量", projectiles)
        form.addRow("初速 m/s", velocity)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.selected_ammo = Ammo(
            "manual",
            name.text().strip() or "自定义弹药",
            name.text().strip() or "自定义",
            caliber.text().strip() or "自定义",
            damage.value(),
            penetration.value(),
            armor_damage.value(),
            projectiles.value(),
            velocity.value(),
            source_version="manual-user-input",
        )
        self.ammo_card.setText(
            f"<b>{self.selected_ammo.name}</b><br>伤害：{damage.value():g}"
            f"<br>穿深：{penetration.value():g}<br>甲伤：{armor_damage.value():g}%"
            "<br>数据版本：用户手动输入"
        )
        self._schedule_analysis()

    def _load_preset(self, index: int) -> None:
        values = list(default_armor_presets().values())
        if not 0 <= index < len(values):
            return
        self.layers = [layer.clone() for layer in values[index]]
        self._refresh_layers()

    def _choose_preset(self, index: int) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)
        self._load_preset(index)
        self.status.setText(f"已一键载入：{self.preset_combo.itemText(index)}")

    def _confirm_armor_layer(self) -> None:
        type_button = self.armor_type_group.checkedButton()
        class_button = self.armor_class_group.checkedButton()
        material_button = self.material_group.checkedButton()
        if not type_button or not class_button or not material_button:
            QMessageBox.warning(self, "缺少选择", "请选择护甲类型、等级和材质")
            return
        layer_type = ArmorLayerType(type_button.property("armor_type"))
        armor_class = int(class_button.property("armor_class"))
        material = ArmorMaterial(material_button.property("material"))
        material_name = material_button.text()
        type_name = type_button.text()
        original = float(20 + armor_class * 6)
        destructibility = {
            ArmorMaterial.CERAMIC: 0.80,
            ArmorMaterial.STEEL: 0.35,
            ArmorMaterial.UHMWPE: 0.45,
            ArmorMaterial.ARAMID: 0.30,
            ArmorMaterial.TITANIUM: 0.50,
            ArmorMaterial.COMBINED: 0.55,
        }.get(material, 0.50)
        index = len(self.layers) + 1
        self.layers.append(
            ArmorLayer(
                f"quick-{index}",
                f"{armor_class}级{material_name}{type_name}",
                layer_type,
                armor_class,
                original,
                original,
                original,
                material,
                destructibility,
                0.18 if layer_type == ArmorLayerType.SOFT else 0.10,
                layer_type != ArmorLayerType.SOFT,
            )
        )
        self._refresh_layers()
        self.layer_table.selectRow(len(self.layers) - 1)
        self.status.setText(f"已添加第 {index} 层，可继续选择并添加下一层")

    def _reset_ammo(self) -> None:
        self.global_search.setText("M855A1")
        self.caliber_filter.setCurrentIndex(0)
        self.status.setText("弹药已重置为 M855A1")

    def _reset_armor(self) -> None:
        self.layers.clear()
        self._refresh_layers()
        self.current_result = None
        self.current_scenario = None
        self.penetration_metric.setText("— · 请添加护甲")
        self.conclusion.setText("选择护甲类型、等级和材质，然后点击“确认并添加”。")
        for value in self.result_values.values():
            value.setText("—")
        self.plot.clear()
        self.layer_details.clear()
        self.status.setText("护甲层已清空，请选择等级和材质添加第 1 层")

    def _reset_all(self) -> None:
        self.distance.setValue(0)
        self.shots.setValue(3)
        self._reset_ammo()
        self._reset_armor()
        self.status.setText("全部已重置：弹药为 M855A1，护甲层为空")

    def _refresh_layers(self) -> None:
        self.layer_table.setRowCount(len(self.layers))
        for row, layer in enumerate(self.layers):
            values = (
                str(row + 1),
                layer.name,
                str(layer.armor_class),
                layer.material.value,
                f"{layer.current_durability:.1f}/{layer.original_max_durability:.1f}",
                f"{layer.true_durability_ratio:.0%}",
            )
            for col, value in enumerate(values):
                self.layer_table.setItem(row, col, QTableWidgetItem(value))
        self.layer_table.resizeColumnsToContents()
        if self.layers:
            self.layer_table.selectRow(0)
            layer = self.layers[0]
            self.durability_slider.blockSignals(True)
            self.durability_slider.setRange(0, round(layer.original_max_durability * 10))
            self.durability_slider.setValue(round(layer.current_durability * 10))
            self.durability_slider.blockSignals(False)
            self._update_durability_label(layer)
        else:
            self.durability_label.setText("尚未添加护甲层")
            self.durability_slider.setRange(0, 0)
        self.confirm_layer_button.setText(f"确认并添加为第 {len(self.layers) + 1} 层")
        self._schedule_analysis()

    def _layer_selection_changed(
        self, current_row: int, _current_column: int, _previous_row: int, _previous_column: int
    ) -> None:
        if not 0 <= current_row < len(self.layers):
            return
        layer = self.layers[current_row]
        self.durability_slider.blockSignals(True)
        self.durability_slider.setRange(0, round(layer.original_max_durability * 10))
        self.durability_slider.setValue(round(layer.current_durability * 10))
        self.durability_slider.blockSignals(False)
        self._update_durability_label(layer)

    def _durability_changed(self, value: int) -> None:
        row = max(0, self.layer_table.currentRow())
        if not self.layers or row >= len(self.layers):
            return
        layer = self.layers[row]
        layer.current_durability = min(value / 10, layer.displayed_max_durability)
        self._update_durability_label(layer)
        self._refresh_layers_without_selection()
        self._schedule_analysis()

    def _refresh_layers_without_selection(self) -> None:
        row = max(0, self.layer_table.currentRow())
        for idx, layer in enumerate(self.layers):
            self.layer_table.setItem(
                idx, 4, QTableWidgetItem(f"{layer.current_durability:.1f}/{layer.original_max_durability:.1f}")
            )
            self.layer_table.setItem(idx, 5, QTableWidgetItem(f"{layer.true_durability_ratio:.0%}"))
        self.layer_table.selectRow(row)

    def _update_durability_label(self, layer: ArmorLayer) -> None:
        self.durability_label.setText(
            f"当前 {layer.current_durability:.1f} · 维修上限 {layer.displayed_max_durability:.1f}"
            f" · 出厂 {layer.original_max_durability:.1f} · 真实防护比 {layer.true_durability_ratio:.0%}"
        )

    def _add_layer(self) -> None:
        index = len(self.layers) + 1
        self.layers.append(
            ArmorLayer(
                f"custom{index}",
                f"自定义 {index} 层",
                ArmorLayerType.PLATE,
                4,
                40,
                40,
                40,
                ArmorMaterial.UNKNOWN,
                0.5,
                0.12,
                True,
            )
        )
        self._refresh_layers()

    def _edit_layer(self) -> None:
        row = self.layer_table.currentRow()
        if not 0 <= row < len(self.layers):
            return
        layer = self.layers[row]
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑护甲层")
        form = QFormLayout(dialog)
        name = QLineEdit(layer.name)
        armor_class = QSpinBox()
        armor_class.setRange(1, 6)
        armor_class.setValue(layer.armor_class)
        material = QComboBox()
        for value in ArmorMaterial:
            material.addItem(value.value, value)
        material.setCurrentIndex(list(ArmorMaterial).index(layer.material))
        original = QDoubleSpinBox()
        original.setRange(0.1, 500)
        original.setValue(layer.original_max_durability)
        repair = QDoubleSpinBox()
        repair.setRange(0.1, 500)
        repair.setValue(layer.displayed_max_durability)
        current = QDoubleSpinBox()
        current.setRange(0, 500)
        current.setValue(layer.current_durability)
        destructibility = QDoubleSpinBox()
        destructibility.setRange(0.01, 3)
        destructibility.setSingleStep(0.05)
        destructibility.setValue(layer.destructibility)
        blunt = QDoubleSpinBox()
        blunt.setRange(0, 1)
        blunt.setSingleStep(0.01)
        blunt.setValue(layer.blunt_throughput)
        form.addRow("名称", name)
        form.addRow("等级", armor_class)
        form.addRow("材料", material)
        form.addRow("出厂耐久", original)
        form.addRow("维修上限", repair)
        form.addRow("当前耐久", current)
        form.addRow("材料破坏系数", destructibility)
        form.addRow("钝伤透过率", blunt)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if repair.value() > original.value() or current.value() > repair.value():
            QMessageBox.warning(self, "参数错误", "必须满足：当前耐久 ≤ 维修上限 ≤ 出厂耐久")
            return
        try:
            self.layers[row] = ArmorLayer(
                layer.id,
                name.text().strip() or layer.name,
                layer.layer_type,
                armor_class.value(),
                current.value(),
                repair.value(),
                original.value(),
                material.currentData(),
                destructibility.value(),
                blunt.value(),
                layer.is_hard_armor,
                layer.protection_zones,
                layer.enabled,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "参数错误", str(exc))
            return
        self._refresh_layers()

    def _remove_layer(self) -> None:
        row = self.layer_table.currentRow()
        if 0 <= row < len(self.layers):
            self.layers.pop(row)
            self._refresh_layers()

    def _save_preset(self) -> None:
        if not self.layers:
            return
        name = f"用户预设 {len(self.layers)} 层"
        self.database.save_preset(name, tuple(self.layers))
        self.status.setText(f"已保存：{name}")

    def _scenario(self, iterations: int | None = None) -> ShotScenario:
        if self.selected_ammo is None:
            raise ValueError("请先选择弹药")
        if not self.layers:
            raise ValueError("请至少添加一层护甲")
        return ShotScenario(
            ammo=self.selected_ammo,
            armor_layers=tuple(layer.clone() for layer in self.layers),
            body_part=BodyPart.THORAX,
            distance_m=self.distance.value(),
            shot_count=self.shots.value(),
            simulation_iterations=iterations or int(self.iterations.currentData()),
            random_seed=20260730,
        )

    def _schedule_analysis(self, *_args) -> None:
        if not hasattr(self, "penetration_metric"):
            return
        if not hasattr(self, "analysis_timer"):
            self.analysis_timer = QTimer(self)
            self.analysis_timer.setSingleShot(True)
            self.analysis_timer.timeout.connect(self._analyze)
        self.analysis_timer.start(45)

    def _analyze(self) -> None:
        try:
            from .engine import analyze

            scenario = self._scenario()
            self.current_scenario = scenario
            self.current_result = analyze(scenario, self.ruleset)
            self._show_result(self.current_result)
        except ValueError as exc:
            self.status.setText(str(exc))

    def _show_result(self, result) -> None:
        probability = result.final_penetration_probability
        level = (
            "极低" if probability < 0.15 else
            "较低" if probability < 0.35 else
            "五五开" if probability < 0.65 else
            "较高" if probability < 0.85 else "极高"
        )
        first = result.expected_first_penetration_shot
        kill = result.kill_probability_by_shot[-1] if result.kill_probability_by_shot else 0
        self.penetration_metric.setText(f"{probability:.1%} · {level}")
        self.result_values["three"].setText(
            f"{result.three_shot_penetration_probability:.1%}"
        )
        self.result_values["first"].setText(
            f"第 {first:.1f} 发" if first is not None else "未观察到"
        )
        self.result_values["health"].setText(f"{result.expected_health_damage:.1f}")
        self.result_values["blunt"].setText(f"{result.expected_blunt_damage:.1f}")
        self.result_values["kill"].setText(f"{kill:.1%}")
        self.result_values["confidence"].setText(result.confidence.value)
        first_line = (
            f"预计首次穿透：{first:.1f} 发\n"
            if first is not None
            else "预计首次穿透：本次范围内未观察到\n"
        )
        self.result_grid.setText(
            f"期望肉体伤害：{result.expected_health_damage:.1f}\n"
            f"未穿透钝伤：{result.expected_blunt_damage:.1f}\n"
            f"单次总期望伤害：{result.expected_total_damage:.1f}\n"
            f"3 发内至少一次穿透：{result.three_shot_penetration_probability:.1%}\n"
            + first_line
        )
        self.result_grid.setText(
            self.result_grid.text()
            + f"{len(result.kill_probability_by_shot)} 发胸部致死概率：{kill:.1%}\n"
            + f"数据版本：{result.data_version}\n规则版本：{result.ruleset_version}\n"
            + f"可信度：{result.confidence.value}"
        )
        self.conclusion.setText(result_summary(result, self.shots.value()))
        details = []
        for idx, layer in enumerate(result.layer_results, 1):
            details.append(
                f"<b>{idx}. {layer.name}</b>　条件穿透 {layer.conditional_penetration_probability:.1%}"
                f"　累计穿透 {layer.cumulative_penetration_probability:.1%}"
                f"　在本层停止 {layer.stop_probability:.1%}<br>"
                f"预计耐久损失 {layer.expected_durability_loss:.2f}　射后耐久 {layer.expected_durability_after:.1f}"
                f"　穿透后伤害 {layer.remaining_damage:.1f}　穿透后穿深 {layer.remaining_penetration:.1f}"
            )
        self.layer_details.setText("<hr>".join(details) or "无护甲层")
        self._plot_result(result)
        self.status.setText("结果已刷新")

    def _plot_result(self, result) -> None:
        self.plot.clear()
        shots = list(range(1, len(result.penetration_probability_by_shot) + 1))
        if shots:
            self.plot.plot(
                shots,
                [p * 100 for p in result.penetration_probability_by_shot],
                pen=pg.mkPen("#eac879", width=2),
                symbol="o",
                name="穿透率 %",
            )
        for idx in range(len(self.layers)):
            values = [
                snap.durability[idx]
                for snap in result.durability_timeline
                if idx < len(snap.durability)
            ]
            if values:
                self.plot.plot(
                    list(range(len(values))),
                    values,
                    pen=pg.mkPen(pg.intColor(idx, hues=max(1, len(self.layers))), width=2),
                )

    def _run_simulation(self) -> None:
        if self.worker is not None:
            self.worker.cancelled = True
        try:
            scenario = self._scenario(int(self.iterations.currentData()))
        except ValueError as exc:
            QMessageBox.warning(self, "参数错误", str(exc))
            return
        self.current_scenario = scenario
        self.worker = SimulationWorker(scenario, self.ruleset)
        self.worker.signals.progress.connect(self.progress.setValue)
        self.worker.signals.result.connect(self._simulation_result)
        self.worker.signals.error.connect(self._simulation_error)
        self.worker.signals.finished.connect(self._simulation_finished)
        self.progress.setValue(0)
        self.progress.show()
        self.simulate_button.setEnabled(False)
        self.status.setText("后台模拟中，界面仍可操作…")
        self.thread_pool.start(self.worker)

    def _simulation_result(self, result) -> None:
        self.current_result = result
        self._show_result(result)

    def _simulation_error(self, message: str) -> None:
        if message != "模拟已取消":
            QMessageBox.warning(self, "模拟错误", message)
            LOGGER.error("Simulation failed: %s", message)

    def _simulation_finished(self) -> None:
        self.progress.hide()
        self.simulate_button.setEnabled(True)
        self.worker = None

    def _ruleset_changed(self) -> None:
        self.ruleset = (
            ExperimentalRuleset()
            if self.ruleset_combo.currentData() == "experimental"
            else CurrentApproximation()
        )
        self._schedule_analysis()

    def _toggle_lab(self) -> None:
        visible = not self.lab_ruleset_row.isVisible()
        self.lab_ruleset_row.setVisible(visible)
        self.iterations.setVisible(visible)
        self.iterations_label.setVisible(visible)
        self.simulate_button.setVisible(visible)
        self.manual_ammo_button.setVisible(visible)
        self.layer_actions.setVisible(visible)
        self.mode_button.setText("实验室模式" if visible else "快速模式")

    def _toggle_compact(self) -> None:
        compact = self.width() > 760
        if compact:
            self.resize(720, 460)
            self.splitter.setSizes([220, 240, 340])
        else:
            self.resize(1440, 900)
            self.splitter.setSizes([330, 440, 670])

    def _toggle_pin(self) -> None:
        pinned = not bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        self.pin_button.setText("置顶：开" if pinned else "置顶：关")
        self.show()

    def _focus_results(self) -> None:
        self.results_panel.setFocus()

    def _refresh_compare(self) -> None:
        if not self.layers:
            return
        from .engine import analyze

        rows = []
        for ammo in self.database.all_ammo():
            scenario = ShotScenario(
                ammo=ammo, armor_layers=tuple(x.clone() for x in self.layers), shot_count=3
            )
            result = analyze(scenario, self.ruleset)
            first = result.expected_first_penetration_shot or 0
            rows.append(
                (
                    ammo.short_name,
                    ammo.caliber,
                    result.final_penetration_probability,
                    result.three_shot_penetration_probability,
                    first,
                    result.expected_health_damage,
                    result.expected_blunt_damage,
                )
            )
        self.compare_table.setSortingEnabled(False)
        self.compare_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                display = (
                    f"{value:.1%}" if col in (2, 3) else
                    f"{value:.1f}" if isinstance(value, float) else str(value)
                )
                item = QTableWidgetItem(display)
                if isinstance(value, (int, float)):
                    item.setData(Qt.ItemDataRole.UserRole, value)
                self.compare_table.setItem(row, col, item)
        self.compare_table.setSortingEnabled(True)
        self.compare_table.resizeColumnsToContents()

    def _export(self, kind: str) -> None:
        if self.current_result is None or self.current_scenario is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", f"tarkov-result.{kind}", f"{kind.upper()} (*.{kind})"
        )
        if not path:
            return
        if kind == "csv":
            export_csv(Path(path), self.current_scenario, self.current_result)
        else:
            export_json(Path(path), self.current_scenario, self.current_result)
        self.status.setText(f"已导出 {path}")

    def _restore_settings(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        if self.worker:
            self.worker.cancelled = True
        self.settings.setValue("geometry", self.saveGeometry())
        if self.selected_ammo:
            self.settings.setValue("last_ammo", self.selected_ammo.id)
        self.settings.setValue("last_preset", self.preset_combo.currentIndex())
        super().closeEvent(event)


def create_application(database: Database) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Tarkov Armor Simulator")
    app.setOrganizationName("OpenAI")
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow(database)
    return app, window
