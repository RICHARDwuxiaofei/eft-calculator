from __future__ import annotations

import logging
import os
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
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

from .data import DATA_VERSION, Database, default_armor_presets, default_database_path
from .i18n import I18n
from .models import Ammo, ArmorLayer, ArmorLayerType, ArmorMaterial, BodyPart, ShotScenario
from .rulesets import CurrentApproximation, ExperimentalRuleset
from .services import export_csv, export_json, result_summary
from .sync import SnapshotStore, run_sync
from .worker import SimulationWorker

LOGGER = logging.getLogger(__name__)
RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"


def resource_path(*parts: str) -> Path:
    return RESOURCE_ROOT.joinpath(*parts)


STYLE = """
QWidget { background: #101418; color: #eef0f2; font-size: 14px; }
QMainWindow { background: #0b0e11; }
QFrame#card { background: #171c21; border: 1px solid #303840; border-radius: 10px; }
QFrame#hero { background: #1d242b; border: 1px solid #bd9958; border-radius: 12px; }
QFrame#metricCard { background: #14191e; border: 1px solid #2d363e; border-radius: 8px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QTableWidget {
  background: #0d1115; border: 1px solid #3b454f; border-radius: 7px; padding: 7px;
}
QPushButton { background: #252d34; border: 1px solid #46515c; border-radius: 7px; padding: 8px 11px; }
QPushButton:hover { background: #38434d; }
QPushButton:checked, QPushButton#primary { background: #c39b52; color: #101316; font-weight: 800; }
QPushButton#ghost { background: transparent; border-color: #38424b; }
QPushButton#choice { text-align: left; min-height: 36px; }
QLabel#title { font-size: 21px; font-weight: 850; }
QLabel#section { font-size: 16px; font-weight: 800; }
QLabel#muted { color: #99a4ad; }
QLabel#metric { font-size: 48px; font-weight: 900; color: #f2c86f; }
QLabel#metricValue { font-size: 20px; font-weight: 800; }
QTabWidget::pane { border: 1px solid #303840; border-radius: 7px; }
QTabBar::tab { padding: 8px 15px; background: #1d2329; }
QTabBar::tab:selected { background: #343d46; color: #efc873; }
QProgressBar { border: 1px solid #3b424c; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #b89655; }
"""


class SyncSignals(QObject):
    result = Signal(object)


class SyncWorker(QRunnable):
    def __init__(self, store: SnapshotStore, force: bool) -> None:
        super().__init__()
        self.store = store
        self.force = force
        self.signals = SyncSignals()

    @Slot()
    def run(self) -> None:
        self.signals.result.emit(run_sync(self.store, force=self.force))


class MainWindow(QMainWindow):
    """Two-region progressive UI: compact query rail plus a result workspace."""

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.settings = QSettings("EFTCalculator", "EFTCalculator")
        requested_locale = os.getenv("EFT_CALCULATOR_LANG") or str(
            self.settings.value("language", "system")
        )
        self.i18n = I18n(requested_locale)
        self.ruleset = CurrentApproximation()
        self.ammo_items: list[Ammo] = []
        self.selected_ammo: Ammo | None = None
        self.layers: list[ArmorLayer] = []
        self.current_result = None
        self.current_scenario: ShotScenario | None = None
        self.worker: SimulationWorker | None = None
        self.sync_worker: SyncWorker | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self._updating_durability = False
        self._lab_mode = False
        self._analysis_timer = QTimer(self)
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.setInterval(120)
        self._analysis_timer.timeout.connect(self._analyze)
        self.setWindowTitle(self._t("EFT Calculator · 分层护甲与弹药模拟"))
        self.setWindowIcon(QIcon(str(resource_path("icons", "app-icon.png"))))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 680)
        self._build_ui()
        self._apply_i18n()
        self._build_shortcuts()
        self._restore_settings()
        self._refresh_ammo()
        self._reset_all()
        QTimer.singleShot(900, self._load_cached_snapshot)

    def _t(self, source: str, **values: object) -> str:
        return self.i18n.translate(source, **values)

    def _translate_widget_tree(self, root: QWidget) -> None:
        widgets = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            if widget.windowTitle():
                widget.setWindowTitle(self._t(widget.windowTitle()))
            if isinstance(widget, QAbstractButton) and widget.text():
                widget.setText(self._t(widget.text()))
            if isinstance(widget, QLabel) and widget.text():
                widget.setText(self._t(widget.text()))
            if isinstance(widget, QLineEdit) and widget.placeholderText():
                widget.setPlaceholderText(self._t(widget.placeholderText()))
            if isinstance(widget, QComboBox):
                for index in range(widget.count()):
                    widget.setItemText(index, self._t(widget.itemText(index)))
            if isinstance(widget, QTabWidget):
                for index in range(widget.count()):
                    widget.setTabText(index, self._t(widget.tabText(index)))
            if isinstance(widget, QTableWidget):
                for column in range(widget.columnCount()):
                    header = widget.horizontalHeaderItem(column)
                    if header:
                        header.setText(self._t(header.text()))

    def _apply_i18n(self) -> None:
        self._translate_widget_tree(self)

    def _change_language(self, locale: str) -> None:
        self.i18n.set_locale(locale)
        self.settings.setValue("language", self.i18n.locale)
        self._apply_i18n()
        self._refresh_ammo()
        self._refresh_layers()
        if self.selected_ammo:
            self._render_selected_ammo()
        if self.current_result is not None:
            self._show_result(self.current_result)

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 10, 12, 8)
        outer.setSpacing(8)

        top = QHBoxLayout()
        brand = QLabel("EFT CALCULATOR")
        brand.setObjectName("title")
        top.addWidget(brand)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("搜索弹药、简称、别名或口径  ·  Ctrl+K")
        self.global_search.setClearButtonEnabled(True)
        self.global_search.textChanged.connect(self._refresh_ammo)
        self.global_search.returnPressed.connect(self._open_ammo_search)
        top.addWidget(self.global_search, 1)
        self.mode_button = QPushButton("快速")
        self.mode_button.setCheckable(True)
        self.mode_button.clicked.connect(self._toggle_lab)
        top.addWidget(self.mode_button)
        self.favorites_button = QPushButton("★ 收藏")
        self.favorites_button.clicked.connect(lambda: self._open_ammo_search(favorites=True))
        top.addWidget(self.favorites_button)
        self.sync_button = QPushButton("数据 · 内置")
        self.sync_button.clicked.connect(self._sync_now)
        top.addWidget(self.sync_button)
        settings_button = QPushButton("设置")
        settings_button.clicked.connect(self._show_data_settings)
        top.addWidget(settings_button)
        outer.addLayout(top)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.input_panel = self._build_input_rail()
        left_scroll.setWidget(self.input_panel)
        left_scroll.setMinimumWidth(360)
        left_scroll.setMaximumWidth(440)
        self.results_panel = self._build_results_workspace()
        self.splitter.addWidget(left_scroll)
        self.splitter.addWidget(self.results_panel)
        self.splitter.setSizes([400, 1000])
        self.splitter.setStretchFactor(1, 1)
        outer.addWidget(self.splitter, 1)

        footer = QHBoxLayout()
        self.status = QLabel("就绪 · 计算结果为社区近似")
        self.status.setObjectName("muted")
        footer.addWidget(self.status, 1)
        self.data_version_label = QLabel(DATA_VERSION)
        self.data_version_label.setObjectName("muted")
        footer.addWidget(self.data_version_label)
        outer.addLayout(footer)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)
        self.search_dialog = self._build_search_dialog()
        self.armor_dialog = self._build_armor_dialog()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 11, 12, 11)
        label = QLabel(title)
        label.setObjectName("section")
        layout.addWidget(label)
        return frame, layout

    def _build_input_rail(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 0, 5, 0)
        layout.setSpacing(8)

        ammo_card, ammo_layout = self._card("弹药")
        self.selected_ammo_button = QPushButton("选择弹药  ›")
        self.selected_ammo_button.setObjectName("choice")
        self.selected_ammo_button.setMinimumHeight(68)
        self.selected_ammo_button.clicked.connect(self._open_ammo_search)
        ammo_layout.addWidget(self.selected_ammo_button)
        ammo_actions = QHBoxLayout()
        self.favorite_button = QPushButton("☆ 收藏当前")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        reset_ammo = QPushButton("重置弹药")
        reset_ammo.clicked.connect(self._reset_ammo)
        ammo_actions.addWidget(self.favorite_button)
        ammo_actions.addWidget(reset_ammo)
        ammo_layout.addLayout(ammo_actions)
        layout.addWidget(ammo_card)

        armor_card, armor_layout = self._card("护甲命中路径")
        preset_row = QGridLayout()
        for index, name in enumerate(default_armor_presets()):
            button = QPushButton(name.replace(" + ", "\n+ "))
            button.setMinimumHeight(54)
            button.clicked.connect(lambda _checked=False, value=index: self._choose_preset(value))
            preset_row.addWidget(button, index // 2, index % 2)
        armor_layout.addLayout(preset_row)
        self.path_summary = QLabel("尚未添加护甲")
        self.path_summary.setWordWrap(True)
        self.path_summary.setObjectName("muted")
        armor_layout.addWidget(self.path_summary)
        path_actions = QHBoxLayout()
        edit_path = QPushButton("编辑路径…")
        edit_path.setObjectName("primary")
        edit_path.clicked.connect(self._open_armor_editor)
        reset_armor = QPushButton("重置护甲")
        reset_armor.clicked.connect(self._reset_armor)
        path_actions.addWidget(edit_path)
        path_actions.addWidget(reset_armor)
        armor_layout.addLayout(path_actions)
        layout.addWidget(armor_card)

        durability_card, durability_layout = self._card("当前层耐久")
        self.durability_label = QLabel("请先添加护甲")
        self.durability_label.setObjectName("muted")
        durability_layout.addWidget(self.durability_label)
        durability_row = QHBoxLayout()
        self.durability_slider = QSlider(Qt.Orientation.Horizontal)
        self.durability_slider.setRange(0, 1000)
        self.durability_slider.valueChanged.connect(self._durability_changed)
        self.durability_spin = QDoubleSpinBox()
        self.durability_spin.setDecimals(1)
        self.durability_spin.setSingleStep(1)
        self.durability_spin.setFixedWidth(86)
        self.durability_spin.valueChanged.connect(self._durability_spin_changed)
        durability_row.addWidget(self.durability_slider, 1)
        durability_row.addWidget(self.durability_spin)
        durability_layout.addLayout(durability_row)
        quick_row = QHBoxLayout()
        for title, ratio in (("新品", 1.0), ("75", 0.75), ("50", 0.5), ("25", 0.25), ("损坏", 0.0)):
            button = QPushButton(title)
            button.setObjectName("ghost")
            button.clicked.connect(
                lambda _checked=False, current=ratio: self._set_durability_ratio(current)
            )
            quick_row.addWidget(button)
        durability_layout.addLayout(quick_row)
        layout.addWidget(durability_card)

        scenario_card, scenario_layout = self._card("射击条件")
        conditions = QFormLayout()
        self.distance = QSpinBox()
        self.distance.setRange(0, 1000)
        self.distance.setSuffix(" m")
        self.distance.valueChanged.connect(self._schedule_analysis)
        self.shots = QSpinBox()
        self.shots.setRange(1, 100)
        self.shots.setValue(3)
        self.shots.valueChanged.connect(self._schedule_analysis)
        conditions.addRow("距离", self.distance)
        conditions.addRow("连续射击", self.shots)
        scenario_layout.addLayout(conditions)

        self.advanced_button = QPushButton("高级参数  ›")
        self.advanced_button.setCheckable(True)
        self.advanced_button.clicked.connect(self._toggle_advanced)
        scenario_layout.addWidget(self.advanced_button)
        self.advanced_panel = QWidget()
        advanced_form = QFormLayout(self.advanced_panel)
        advanced_form.setContentsMargins(0, 4, 0, 0)
        self.iterations = QComboBox()
        self.iterations.addItem("1,000（快速）", 1000)
        self.iterations.addItem("10,000（标准）", 10000)
        self.iterations.addItem("100,000（高精度）", 100000)
        self.ruleset_combo = QComboBox()
        self.ruleset_combo.addItem("当前社区近似", "current")
        self.ruleset_combo.addItem("实验性距离强化", "experimental")
        self.ruleset_combo.currentIndexChanged.connect(self._ruleset_changed)
        advanced_form.addRow("蒙特卡洛", self.iterations)
        advanced_form.addRow("规则集", self.ruleset_combo)
        self.simulate_button = QPushButton("运行蒙特卡洛")
        self.simulate_button.setObjectName("primary")
        self.simulate_button.clicked.connect(self._run_simulation)
        advanced_form.addRow(self.simulate_button)
        self.progress = QProgressBar()
        self.progress.hide()
        advanced_form.addRow(self.progress)
        self.advanced_panel.hide()
        scenario_layout.addWidget(self.advanced_panel)
        layout.addWidget(scenario_card)

        reset_all = QPushButton("重置所有")
        reset_all.clicked.connect(self._reset_all)
        layout.addWidget(reset_all)
        layout.addStretch()
        return panel

    def _build_results_workspace(self) -> QWidget:
        panel, layout = self._card("计算结果")
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_text = QVBoxLayout()
        hero_label = QLabel("首发穿过全部护甲并到达人体")
        hero_label.setObjectName("muted")
        self.penetration_metric = QLabel("—")
        self.penetration_metric.setObjectName("metric")
        self.conclusion = QLabel("选择弹药和护甲后自动计算")
        self.conclusion.setWordWrap(True)
        hero_text.addWidget(hero_label)
        hero_text.addWidget(self.penetration_metric)
        hero_text.addWidget(self.conclusion)
        hero_layout.addLayout(hero_text, 1)
        self.result_context = QLabel("快速模式\n社区近似")
        self.result_context.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.result_context.setObjectName("muted")
        hero_layout.addWidget(self.result_context)
        layout.addWidget(hero)

        metrics = QGridLayout()
        self.result_values: dict[str, QLabel] = {}
        for index, (key, title) in enumerate(
            (
                ("three", "3 发内至少穿透一次"),
                ("first", "预计首次穿透"),
                ("health", "首发期望肉伤"),
                ("blunt", "首发期望钝伤"),
                ("kill", "连续射击致死概率"),
                ("confidence", "规则可信度"),
            )
        ):
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QVBoxLayout(card)
            label = QLabel(title)
            label.setObjectName("muted")
            value = QLabel("—")
            value.setObjectName("metricValue")
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            metrics.addWidget(card, index // 3, index % 3)
            self.result_values[key] = value
        layout.addLayout(metrics)

        self.result_tabs = QTabWidget()
        self.result_tabs.addTab(self._build_layer_tab(), "分层")
        self.result_tabs.addTab(self._build_burst_tab(), "连续射击")
        self.result_tabs.addTab(self._build_chart_tab(), "图表")
        self.result_tabs.addTab(self._build_compare_tab(), "比较")
        self.result_tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.result_tabs, 1)
        exports = QHBoxLayout()
        exports.addStretch()
        export_csv_button = QPushButton("导出 CSV")
        export_csv_button.clicked.connect(lambda: self._export("csv"))
        export_json_button = QPushButton("导出 JSON")
        export_json_button.clicked.connect(lambda: self._export("json"))
        exports.addWidget(export_csv_button)
        exports.addWidget(export_json_button)
        layout.addLayout(exports)
        return panel

    def _build_layer_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.layer_result_table = QTableWidget(0, 7)
        self.layer_result_table.setHorizontalHeaderLabels(
            ["层", "条件穿透", "累计穿透", "停止", "耐久损失", "剩余伤害", "剩余穿深"]
        )
        self.layer_result_table.verticalHeader().hide()
        layout.addWidget(self.layer_result_table)
        return page

    def _build_burst_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.burst_table = QTableWidget(0, 4)
        self.burst_table.setHorizontalHeaderLabels(["发次", "本发穿透", "累计致死", "各层平均耐久"])
        self.burst_table.verticalHeader().hide()
        layout.addWidget(self.burst_table)
        return page

    def _build_chart_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        pg.setConfigOption("background", "#101418")
        pg.setConfigOption("foreground", "#aeb7bf")
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("left", "概率 / 耐久比例")
        self.plot.setLabel("bottom", "射击次数")
        layout.addWidget(self.plot)
        return page

    def _build_compare_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel("按当前护甲路径对本地弹药库即时排序；双击弹药可设为当前选择。")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.compare_table = QTableWidget(0, 6)
        self.compare_table.setHorizontalHeaderLabels(
            ["弹药", "口径", "首发穿透", "3 发内", "期望首穿", "首发肉伤"]
        )
        self.compare_table.verticalHeader().hide()
        self.compare_table.setSortingEnabled(True)
        self.compare_table.cellDoubleClicked.connect(self._use_compare_ammo)
        layout.addWidget(self.compare_table)
        return page

    def _build_search_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("选择弹药")
        dialog.resize(760, 620)
        layout = QVBoxLayout(dialog)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("名称 / 简称 / 别名 / 口径")
        self.search_input.textChanged.connect(self._search_dialog_changed)
        layout.addWidget(self.search_input)
        self.caliber_filter = QComboBox()
        self.caliber_filter.addItem("全部口径", "")
        for caliber in ("5.56x45", "5.45x39", "7.62x39", "7.62x51", "12/70"):
            self.caliber_filter.addItem(caliber, caliber)
        self.caliber_filter.currentIndexChanged.connect(self._refresh_ammo)
        self.caliber_filter.hide()
        self.caliber_group = QButtonGroup(self)
        self.caliber_group.setExclusive(True)
        caliber_row = QHBoxLayout()
        for index in range(self.caliber_filter.count()):
            button = QPushButton(self.caliber_filter.itemText(index))
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, value=index: self.caliber_filter.setCurrentIndex(value)
            )
            self.caliber_group.addButton(button, index)
            caliber_row.addWidget(button)
        self.caliber_group.button(0).setChecked(True)
        layout.addLayout(caliber_row)
        self.ammo_list = QListWidget()
        self.ammo_list.itemActivated.connect(
            lambda item: self._select_ammo_by_id(item.data(Qt.ItemDataRole.UserRole), close=True)
        )
        self.ammo_list.currentRowChanged.connect(self._select_ammo)
        layout.addWidget(self.ammo_list, 1)
        # Compatibility and touch-friendly quick choices, rebuilt from the first results.
        self.ammo_choice_group = QButtonGroup(self)
        self.ammo_choice_group.setExclusive(True)
        self.ammo_choice_host = QWidget()
        self.ammo_choice_grid = QGridLayout(self.ammo_choice_host)
        layout.addWidget(self.ammo_choice_host)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog

    def _build_armor_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("护甲路径编辑器")
        dialog.resize(720, 620)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("选择类型、等级和材质，确认后会追加为下一层。"))
        type_row = QHBoxLayout()
        self.armor_type_group = QButtonGroup(self)
        self.armor_type_group.setExclusive(True)
        for index, (title, value) in enumerate(
            (("硬插板", ArmorLayerType.PLATE), ("软甲", ArmorLayerType.SOFT), ("头盔", ArmorLayerType.HELMET))
        ):
            button = QPushButton(title)
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
            button = QPushButton(
                self._t("{armor_class} 级", armor_class=armor_class)
            )
            button.setCheckable(True)
            button.setProperty("armor_class", armor_class)
            self.armor_class_group.addButton(button, armor_class)
            chooser.addWidget(button, armor_class, 0)
        self.armor_class_group.button(5).setChecked(True)
        self.material_group = QButtonGroup(self)
        self.material_group.setExclusive(True)
        for row, (title, material) in enumerate(
            (
                ("陶瓷", ArmorMaterial.CERAMIC),
                ("钢", ArmorMaterial.STEEL),
                ("UHMWPE", ArmorMaterial.UHMWPE),
                ("芳纶", ArmorMaterial.ARAMID),
                ("钛", ArmorMaterial.TITANIUM),
                ("复合", ArmorMaterial.COMBINED),
            ),
            1,
        ):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setProperty("material", material)
            button.setIcon(QIcon(str(resource_path("items", "armor", f"{material.value}.png"))))
            button.setIconSize(QSize(36, 36))
            self.material_group.addButton(button, row)
            chooser.addWidget(button, row, 1)
        self.material_group.button(1).setChecked(True)
        layout.addLayout(chooser)
        self.confirm_layer_button = QPushButton("确认并添加为第 1 层")
        self.confirm_layer_button.setObjectName("primary")
        self.confirm_layer_button.clicked.connect(self._confirm_armor_layer)
        layout.addWidget(self.confirm_layer_button)
        action_row = QHBoxLayout()
        move_up = QPushButton("上移")
        move_up.clicked.connect(lambda: self._move_layer(-1))
        move_down = QPushButton("下移")
        move_down.clicked.connect(lambda: self._move_layer(1))
        toggle = QPushButton("启用 / 停用")
        toggle.clicked.connect(self._toggle_layer_enabled)
        remove = QPushButton("删除")
        remove.clicked.connect(self._remove_layer)
        action_row.addWidget(move_up)
        action_row.addWidget(move_down)
        action_row.addWidget(toggle)
        action_row.addWidget(remove)
        layout.addLayout(action_row)
        self.layer_table = QTableWidget(0, 6)
        self.layer_table.setHorizontalHeaderLabels(["层", "名称", "等级", "材质", "当前/出厂", "状态"])
        self.layer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layer_table.currentCellChanged.connect(self._layer_selection_changed)
        self.layer_table.verticalHeader().hide()
        layout.addWidget(self.layer_table)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(default_armor_presets().keys())
        self.preset_combo.hide()
        self.layer_actions = QWidget()
        self.layer_actions.hide()
        return dialog

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_ammo_search)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._toggle_favorite)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._toggle_lab)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self._open_ammo_search)
        QShortcut(QKeySequence("Ctrl+2"), self, activated=self._open_armor_editor)
        QShortcut(QKeySequence("Ctrl+3"), self, activated=self._focus_results)
        QShortcut(QKeySequence("Escape"), self, activated=self.global_search.clear)

    def _refresh_ammo(self, *_args) -> None:
        query = self.global_search.text().strip()
        if hasattr(self, "search_input") and self.search_dialog.isVisible():
            query = self.search_input.text().strip()
        caliber = self.caliber_filter.currentData() if hasattr(self, "caliber_filter") else ""
        self.ammo_items = self.database.search_ammo(query, caliber)
        if not hasattr(self, "ammo_list"):
            return
        current_id = self.selected_ammo.id if self.selected_ammo else None
        self.ammo_list.blockSignals(True)
        self.ammo_list.clear()
        for ammo in self.ammo_items:
            prefix = "★ " if self.database.is_favorite(ammo.id) else ""
            self.ammo_list.addItem(
                f"{prefix}{ammo.short_name:<14}  {ammo.caliber}   "
                + self._t(
                    "伤害 {damage:g} · 穿深 {penetration:g}",
                    damage=ammo.damage,
                    penetration=ammo.penetration_power,
                )
            )
            self.ammo_list.item(self.ammo_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, ammo.id
            )
        self.ammo_list.blockSignals(False)
        self._rebuild_quick_ammo_buttons()
        if current_id:
            for index, ammo in enumerate(self.ammo_items):
                if ammo.id == current_id:
                    self.ammo_list.setCurrentRow(index)
                    break

    def _rebuild_quick_ammo_buttons(self) -> None:
        while self.ammo_choice_grid.count():
            item = self.ammo_choice_grid.takeAt(0)
            if item.widget():
                self.ammo_choice_group.removeButton(item.widget())
                item.widget().deleteLater()
        for index, ammo in enumerate(self.ammo_items[:6]):
            button = QPushButton(
                f"{ammo.short_name}\n"
                + self._t(
                    "伤害 {damage:g} · 穿深 {penetration:g}",
                    damage=ammo.damage,
                    penetration=ammo.penetration_power,
                )
            )
            button.setCheckable(True)
            button.setIcon(QIcon(str(self._ammo_icon(ammo))))
            button.setIconSize(QSize(42, 42))
            button.clicked.connect(
                lambda _checked=False, item_id=ammo.id: self._select_ammo_by_id(item_id)
            )
            self.ammo_choice_group.addButton(button)
            self.ammo_choice_grid.addWidget(button, index // 3, index % 3)

    def _ammo_icon(self, ammo: Ammo) -> Path:
        mapping = {
            "m855a1": "m855a1.png",
            "m855": "m855.png",
            "m995": "m995.png",
            "762bp": "762bp.png",
            "7n40": "7n40.png",
            "545bp": "545bp.png",
            "m80": "m80.png",
            "ap20": "ap20.png",
            "buckshot": "buckshot.png",
        }
        return resource_path("items", "ammo", mapping.get(ammo.id, "m855a1.png"))

    def _search_dialog_changed(self, text: str) -> None:
        self.global_search.blockSignals(True)
        self.global_search.setText(text)
        self.global_search.blockSignals(False)
        self._refresh_ammo()

    def _open_ammo_search(self, *_args, favorites: bool = False) -> None:
        self.search_input.setText("" if favorites else self.global_search.text())
        self._refresh_ammo()
        if favorites:
            for index in reversed(range(self.ammo_list.count())):
                item_id = self.ammo_list.item(index).data(Qt.ItemDataRole.UserRole)
                if not self.database.is_favorite(item_id):
                    self.ammo_list.takeItem(index)
        self.search_input.setFocus()
        self.search_dialog.show()
        self.search_dialog.raise_()

    def _select_ammo(self, row: int) -> None:
        if 0 <= row < len(self.ammo_items):
            self._set_selected_ammo(self.ammo_items[row])

    def _select_ammo_by_id(self, item_id: str, *, close: bool = False) -> None:
        ammo = next((item for item in self.database.all_ammo() if item.id == item_id), None)
        if ammo:
            self._set_selected_ammo(ammo)
        if close:
            self.search_dialog.accept()

    def _set_selected_ammo(self, ammo: Ammo) -> None:
        self.selected_ammo = ammo
        self.database.mark_recent(ammo.id)
        self._render_selected_ammo()
        self._schedule_analysis()

    def _render_selected_ammo(self) -> None:
        ammo = self.selected_ammo
        if ammo is None:
            return
        self.selected_ammo_button.setText(
            self._t(
                "{ammo}  ·  {caliber}\n伤害 {damage:g}    穿深 {penetration:g}    甲伤 {armor_damage:g}%",
                ammo=ammo.short_name,
                caliber=ammo.caliber,
                damage=ammo.damage,
                penetration=ammo.penetration_power,
                armor_damage=ammo.armor_damage_percent,
            )
        )
        self.selected_ammo_button.setIcon(QIcon(str(self._ammo_icon(ammo))))
        self.selected_ammo_button.setIconSize(QSize(48, 48))
        self.favorite_button.setText(
            self._t("★ 已收藏")
            if self.database.is_favorite(ammo.id)
            else self._t("☆ 收藏当前")
        )

    def _toggle_favorite(self) -> None:
        if not self.selected_ammo:
            return
        favorite = not self.database.is_favorite(self.selected_ammo.id)
        self.database.set_favorite(self.selected_ammo.id, favorite)
        self.favorite_button.setText(
            self._t("★ 已收藏") if favorite else self._t("☆ 收藏当前")
        )

    def _choose_preset(self, index: int) -> None:
        self.preset_combo.setCurrentIndex(index)
        preset = list(default_armor_presets().values())[index]
        self.layers = [layer.clone() for layer in preset]
        self._refresh_layers()
        self._schedule_analysis()

    def _open_armor_editor(self) -> None:
        self.armor_dialog.show()
        self.armor_dialog.raise_()

    def _confirm_armor_layer(self) -> None:
        armor_class = self.armor_class_group.checkedButton().property("armor_class")
        material = ArmorMaterial(self.material_group.checkedButton().property("material"))
        layer_type = ArmorLayerType(
            self.armor_type_group.checkedButton().property("armor_type")
        )
        maximum = 30.0 + armor_class * 5.0
        destructibility = {
            ArmorMaterial.CERAMIC: 0.80,
            ArmorMaterial.STEEL: 0.35,
            ArmorMaterial.UHMWPE: 0.45,
            ArmorMaterial.ARAMID: 0.30,
            ArmorMaterial.TITANIUM: 0.42,
            ArmorMaterial.COMBINED: 0.55,
        }[material]
        title = self._t(
            "{armor_class}级{material}",
            armor_class=armor_class,
            material=self.material_group.checkedButton().text(),
        )
        self.layers.append(
            ArmorLayer(
                id=f"custom-{len(self.layers) + 1}",
                name=title,
                layer_type=layer_type,
                armor_class=armor_class,
                current_durability=maximum,
                displayed_max_durability=maximum,
                original_max_durability=maximum,
                material=material,
                destructibility=destructibility,
                blunt_throughput=0.10 if layer_type == ArmorLayerType.PLATE else 0.19,
                is_hard_armor=layer_type != ArmorLayerType.SOFT,
            )
        )
        self._refresh_layers()
        self._schedule_analysis()

    def _refresh_layers(self) -> None:
        self.layer_table.blockSignals(True)
        self.layer_table.setRowCount(len(self.layers))
        path_parts = []
        for row, layer in enumerate(self.layers):
            values = (
                str(row + 1),
                self._t(layer.name),
                str(layer.armor_class),
                layer.material.value,
                f"{layer.current_durability:.1f}/{layer.original_max_durability:.1f}",
                self._t("启用") if layer.enabled else self._t("停用"),
            )
            for column, value in enumerate(values):
                self.layer_table.setItem(row, column, QTableWidgetItem(value))
            path_parts.append(
                f"{row + 1}. {self._t(layer.name)}  "
                f"{layer.current_durability:.0f}/{layer.original_max_durability:.0f}"
                + ("" if layer.enabled else self._t("（停用）"))
            )
        self.layer_table.blockSignals(False)
        self.path_summary.setText(
            "\n".join(path_parts) if path_parts else self._t("尚未添加护甲")
        )
        self.confirm_layer_button.setText(
            self._t("确认并添加为第 {layer} 层", layer=len(self.layers) + 1)
        )
        if self.layers:
            row = min(max(self.layer_table.currentRow(), 0), len(self.layers) - 1)
            self.layer_table.selectRow(row)
            self._load_durability_controls(self.layers[row])
        else:
            self.durability_spin.setRange(0, 0)
            self.durability_label.setText(self._t("请先添加护甲"))

    def _layer_selection_changed(
        self, current_row: int, _current_column: int, _previous_row: int, _previous_column: int
    ) -> None:
        if 0 <= current_row < len(self.layers):
            self._load_durability_controls(self.layers[current_row])

    def _load_durability_controls(self, layer: ArmorLayer) -> None:
        self._updating_durability = True
        self.durability_spin.setRange(0, layer.original_max_durability)
        self.durability_spin.setValue(layer.current_durability)
        self.durability_slider.setValue(
            round(layer.current_durability / layer.original_max_durability * 1000)
        )
        self.durability_label.setText(
            f"{self._t(layer.name)} · "
            f"{layer.current_durability:.1f}/{layer.original_max_durability:.1f}"
        )
        self._updating_durability = False

    def _durability_changed(self, value: int) -> None:
        if self._updating_durability or not self.layers:
            return
        row = max(0, self.layer_table.currentRow())
        layer = self.layers[row]
        layer.current_durability = min(
            layer.displayed_max_durability, layer.original_max_durability * value / 1000
        )
        self._load_durability_controls(layer)
        self._refresh_layers_without_selection()
        self._schedule_analysis()

    def _durability_spin_changed(self, value: float) -> None:
        if self._updating_durability or not self.layers:
            return
        row = max(0, self.layer_table.currentRow())
        layer = self.layers[row]
        layer.current_durability = min(value, layer.displayed_max_durability)
        self._load_durability_controls(layer)
        self._refresh_layers_without_selection()
        self._schedule_analysis()

    def _set_durability_ratio(self, ratio: float) -> None:
        if not self.layers:
            return
        row = max(0, self.layer_table.currentRow())
        layer = self.layers[row]
        layer.current_durability = min(
            layer.displayed_max_durability, layer.original_max_durability * ratio
        )
        self._refresh_layers()
        self._schedule_analysis()

    def _refresh_layers_without_selection(self) -> None:
        current = self.layer_table.currentRow()
        self._refresh_layers()
        if current >= 0:
            self.layer_table.selectRow(current)

    def _add_layer(self) -> None:
        self._confirm_armor_layer()

    def _edit_layer(self) -> None:
        self._open_armor_editor()

    def _remove_layer(self) -> None:
        row = self.layer_table.currentRow()
        if 0 <= row < len(self.layers):
            self.layers.pop(row)
            self._refresh_layers()
            self._schedule_analysis()

    def _move_layer(self, direction: int) -> None:
        row = self.layer_table.currentRow()
        target = row + direction
        if 0 <= row < len(self.layers) and 0 <= target < len(self.layers):
            self.layers[row], self.layers[target] = self.layers[target], self.layers[row]
            self._refresh_layers()
            self.layer_table.selectRow(target)
            self._schedule_analysis()

    def _toggle_layer_enabled(self) -> None:
        row = self.layer_table.currentRow()
        if 0 <= row < len(self.layers):
            self.layers[row].enabled = not self.layers[row].enabled
            self._refresh_layers()
            self._schedule_analysis()

    def _save_preset(self) -> None:
        if self.layers:
            self.database.save_preset(self._t("自定义路径"), tuple(self.layers))

    def _reset_ammo(self) -> None:
        self.global_search.clear()
        ammo = next((item for item in self.database.all_ammo() if item.id == "m855a1"), None)
        if ammo is None:
            ammo = self.database.all_ammo()[0]
        self._set_selected_ammo(ammo)

    def _reset_armor(self) -> None:
        self.layers = []
        self._refresh_layers()
        self.penetration_metric.setText(self._t("— · 请添加护甲"))
        self.conclusion.setText(
            self._t("选择弹药后，使用护甲预设或打开路径编辑器添加第一层。")
        )
        self._schedule_analysis()

    def _reset_all(self) -> None:
        self.distance.setValue(0)
        self.shots.setValue(3)
        self._reset_ammo()
        self._reset_armor()

    def _scenario(self, iterations: int | None = None) -> ShotScenario:
        if not self.selected_ammo or not self.layers:
            raise ValueError(self._t("请先选择弹药并添加护甲"))
        return ShotScenario(
            ammo=self.selected_ammo,
            armor_layers=tuple(layer.clone() for layer in self.layers),
            body_part=BodyPart.THORAX,
            distance_m=self.distance.value(),
            shot_count=self.shots.value(),
            simulation_iterations=iterations or self.iterations.currentData(),
            random_seed=20260731,
        )

    def _schedule_analysis(self, *_args) -> None:
        self._analysis_timer.start()

    def _analyze(self) -> None:
        if not self.selected_ammo or not self.layers:
            self.penetration_metric.setText(self._t("— · 请添加护甲"))
            self.conclusion.setText(
                self._t("选择弹药后，使用护甲预设或打开路径编辑器添加第一层。")
            )
            for value in self.result_values.values():
                value.setText("—")
            return
        from .engine import analyze

        try:
            scenario = self._scenario()
            result = analyze(scenario, self.ruleset)
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.current_scenario = scenario
        self._show_result(result)

    def _show_result(self, result) -> None:
        self.current_result = result
        self.penetration_metric.setText(f"{result.final_penetration_probability:.0%}")
        self.conclusion.setText(result_summary(result, self.shots.value(), self._t))
        self.result_values["three"].setText(f"{result.three_shot_penetration_probability:.0%}")
        first = result.expected_first_penetration_shot
        self.result_values["first"].setText(
            self._t("第 {shot:.1f} 发", shot=first)
            if first
            else self._t("未穿透")
        )
        self.result_values["health"].setText(f"{result.expected_health_damage:.1f}")
        self.result_values["blunt"].setText(f"{result.expected_blunt_damage:.1f}")
        kill = result.kill_probability_by_shot[-1] if result.kill_probability_by_shot else 0
        self.result_values["kill"].setText(f"{kill:.0%}")
        self.result_values["confidence"].setText(result.confidence.value)
        self.result_context.setText(
            f"{self._t('实验室' if self._lab_mode else '快速')} "
            f"{self._t('模式')}\n{result.ruleset_version}\n{result.data_version}"
        )
        self._fill_layer_results(result)
        self._fill_burst_results(result)
        self._plot_result(result)
        self.status.setText(self._t("已自动更新 · 120 ms 防抖"))

    def _fill_layer_results(self, result) -> None:
        self.layer_result_table.setRowCount(len(result.layer_results))
        for row, layer in enumerate(result.layer_results):
            values = (
                layer.name,
                f"{layer.conditional_penetration_probability:.1%}",
                f"{layer.cumulative_penetration_probability:.1%}",
                f"{layer.stop_probability:.1%}",
                f"{layer.expected_durability_loss:.2f}",
                f"{layer.remaining_damage:.1f}",
                f"{layer.remaining_penetration:.1f}",
            )
            for column, value in enumerate(values):
                self.layer_result_table.setItem(row, column, QTableWidgetItem(value))
        self.layer_result_table.resizeColumnsToContents()

    def _fill_burst_results(self, result) -> None:
        probabilities = result.penetration_probability_by_shot
        self.burst_table.setRowCount(len(probabilities))
        for row, probability in enumerate(probabilities):
            snapshot = result.durability_timeline[min(row + 1, len(result.durability_timeline) - 1)]
            kill = result.kill_probability_by_shot[min(row, len(result.kill_probability_by_shot) - 1)]
            values = (
                str(row + 1),
                f"{probability:.1%}",
                f"{kill:.1%}",
                " / ".join(f"{value:.1f}" for value in snapshot.durability),
            )
            for column, value in enumerate(values):
                self.burst_table.setItem(row, column, QTableWidgetItem(value))
        self.burst_table.resizeColumnsToContents()

    def _plot_result(self, result) -> None:
        self.plot.clear()
        shots = list(range(1, len(result.penetration_probability_by_shot) + 1))
        self.plot.plot(
            shots,
            result.penetration_probability_by_shot,
            pen=pg.mkPen("#efc36a", width=3),
            symbol="o",
            name=self._t("穿透率"),
        )
        for index, layer in enumerate(self.layers):
            values = [
                snapshot.durability[index] / layer.original_max_durability
                for snapshot in result.durability_timeline
                if index < len(snapshot.durability)
            ]
            self.plot.plot(
                list(range(len(values))),
                values,
                pen=pg.mkPen(("#68a9d6", "#82c690", "#d77873")[index % 3], width=2),
            )

    def _run_simulation(self) -> None:
        try:
            scenario = self._scenario(self.iterations.currentData())
        except ValueError as exc:
            QMessageBox.information(self, self._t("无法模拟"), str(exc))
            return
        if self.worker:
            self.worker.cancelled = True
        self.worker = SimulationWorker(scenario, self.ruleset)
        self.worker.signals.progress.connect(self.progress.setValue)
        self.worker.signals.result.connect(self._simulation_result)
        self.worker.signals.error.connect(self._simulation_error)
        self.worker.signals.finished.connect(self._simulation_finished)
        self.progress.setValue(0)
        self.progress.show()
        self.simulate_button.setEnabled(False)
        self.thread_pool.start(self.worker)

    def _simulation_result(self, result) -> None:
        self._show_result(result)
        self.status.setText(self._t("蒙特卡洛模拟完成"))

    def _simulation_error(self, message: str) -> None:
        self.status.setText(self._t("模拟失败：{message}", message=message))

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

    def _toggle_lab(self, checked: bool | None = None) -> None:
        self._lab_mode = self.mode_button.isChecked() if checked is not None else not self._lab_mode
        self.mode_button.setChecked(self._lab_mode)
        self.mode_button.setText(self._t("实验室" if self._lab_mode else "快速"))
        self.advanced_button.setChecked(self._lab_mode)
        self._toggle_advanced(self._lab_mode)

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_panel.setVisible(checked)
        self.advanced_button.setText(
            self._t("高级参数  ⌄" if checked else "高级参数  ›")
        )

    def _toggle_compact(self) -> None:
        self.input_panel.setVisible(not self.input_panel.isVisible())

    def _toggle_pin(self) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, not bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        self.show()

    def _focus_results(self) -> None:
        self.results_panel.setFocus()

    def _tab_changed(self, index: int) -> None:
        if index == 3:
            self._refresh_compare()

    def _refresh_compare(self) -> None:
        if not self.layers:
            return
        from .engine import analyze

        rows = []
        for ammo in self.database.all_ammo():
            result = analyze(
                ShotScenario(ammo=ammo, armor_layers=tuple(x.clone() for x in self.layers), shot_count=3),
                self.ruleset,
            )
            rows.append(
                (
                    ammo,
                    result.final_penetration_probability,
                    result.three_shot_penetration_probability,
                    result.expected_first_penetration_shot or 0,
                    result.expected_health_damage,
                )
            )
        self.compare_table.setSortingEnabled(False)
        self.compare_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            ammo, first, three, expected, health = values
            displays = (
                ammo.short_name,
                ammo.caliber,
                f"{first:.1%}",
                f"{three:.1%}",
                f"{expected:.1f}",
                f"{health:.1f}",
            )
            for column, display in enumerate(displays):
                item = QTableWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, ammo.id if column == 0 else values[column - 1] if column > 1 else display)
                self.compare_table.setItem(row, column, item)
        self.compare_table.setSortingEnabled(True)
        self.compare_table.resizeColumnsToContents()

    def _use_compare_ammo(self, row: int, _column: int) -> None:
        item_id = self.compare_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._select_ammo_by_id(item_id)

    def _export(self, kind: str) -> None:
        if self.current_result is None or self.current_scenario is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("导出结果"),
            f"tarkov-result.{kind}",
            f"{kind.upper()} (*.{kind})",
        )
        if not path:
            return
        if kind == "csv":
            export_csv(Path(path), self.current_scenario, self.current_result)
        else:
            export_json(Path(path), self.current_scenario, self.current_result)
        self.status.setText(self._t("已导出 {path}", path=path))

    def _cache_store(self) -> SnapshotStore:
        return SnapshotStore(default_database_path().parent / "data")

    def _load_cached_snapshot(self) -> None:
        store = self._cache_store()
        snapshot = store.read()
        if snapshot:
            self.database.apply_ammo_snapshot(snapshot)
            self.sync_button.setText(
                self._t("数据 · {status}", status=self._t(store.status()))
            )
            self.data_version_label.setText(snapshot["snapshot_id"])
            self._refresh_ammo()
        if store.should_sync():
            self.sync_button.setText(self._t("数据 · 可更新"))
            if os.getenv("QT_QPA_PLATFORM") != "offscreen":
                self._sync_now(force=False)

    def _sync_now(self, *_args, force: bool = True) -> None:
        if self.sync_worker:
            return
        self.sync_button.setEnabled(False)
        self.sync_button.setText(self._t("数据 · 同步中…"))
        self.sync_worker = SyncWorker(self._cache_store(), force)
        self.sync_worker.signals.result.connect(self._sync_finished)
        self.thread_pool.start(self.sync_worker)

    def _sync_finished(self, report) -> None:
        if report.ok:
            snapshot = self._cache_store().read()
            if snapshot:
                self.database.apply_ammo_snapshot(snapshot)
                self.data_version_label.setText(snapshot["snapshot_id"])
                self._refresh_ammo()
            self.sync_button.setText(self._t("数据 · 已更新"))
        else:
            self.sync_button.setText(self._t("数据 · 保留旧版"))
        self.sync_button.setEnabled(True)
        self.status.setText(report.message)
        self.sync_worker = None

    def _show_data_settings(self) -> None:
        store = self._cache_store()
        snapshot = store.read()
        dialog = QDialog(self)
        dialog.setWindowTitle("设置与数据管理")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        overview = QWidget()
        form = QFormLayout(overview)
        language_combo = QComboBox()
        language_combo.addItem("简体中文", "zh_CN")
        language_combo.addItem("English", "en_US")
        language_combo.setCurrentIndex(
            max(0, language_combo.findData(self.i18n.locale))
        )
        language_combo.currentIndexChanged.connect(
            lambda: self._change_language(str(language_combo.currentData()))
        )
        form.addRow("语言", language_combo)
        form.addRow("状态", QLabel(store.status()))
        form.addRow(
            "当前快照",
            QLabel(snapshot.get("snapshot_id") if snapshot else DATA_VERSION),
        )
        form.addRow(
            "最近同步",
            QLabel(snapshot.get("created_at") if snapshot else "尚未在线同步"),
        )
        form.addRow(
            "记录数",
            QLabel(
                str(
                    len(snapshot.get("ammo", []))
                    if snapshot
                    else len(self.database.all_ammo())
                )
            ),
        )
        form.addRow("策略", QLabel("6 小时间隔 · 48 小时过期 · 校验失败保留旧版"))
        tabs.addTab(overview, "概览")
        source_table = QTableWidget(0, 5)
        source_table.setHorizontalHeaderLabels(["来源", "优先级", "记录数", "抓取时间", "URL"])
        sources = snapshot.get("sources", []) if snapshot else []
        source_table.setRowCount(len(sources))
        for row, source in enumerate(sources):
            for column, key in enumerate(
                ("source", "priority", "record_count", "fetched_at", "url")
            ):
                source_table.setItem(row, column, QTableWidgetItem(str(source.get(key, ""))))
        source_table.resizeColumnsToContents()
        tabs.addTab(source_table, "来源清单")
        conflict_table = QTableWidget(0, 6)
        conflict_table.setHorizontalHeaderLabels(
            ["ID", "字段", "采用值", "采用来源", "拒绝值", "拒绝来源"]
        )
        conflicts = snapshot.get("conflicts", []) if snapshot else []
        conflict_table.setRowCount(len(conflicts))
        for row, conflict in enumerate(conflicts):
            for column, key in enumerate(
                (
                    "id",
                    "field",
                    "chosen",
                    "chosen_source",
                    "rejected",
                    "rejected_source",
                )
            ):
                conflict_table.setItem(
                    row, column, QTableWidgetItem(str(conflict.get(key, "")))
                )
        conflict_table.resizeColumnsToContents()
        tabs.addTab(
            conflict_table,
            self._t("冲突记录 ({count})", count=len(conflicts)),
        )
        layout.addWidget(tabs)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        self._translate_widget_tree(dialog)
        dialog.exec()

    def _restore_settings(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        if self.worker:
            self.worker.cancelled = True
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


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
