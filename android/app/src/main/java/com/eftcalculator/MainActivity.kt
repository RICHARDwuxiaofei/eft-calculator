package com.eftcalculator

import android.content.Context
import android.graphics.BitmapFactory
import android.os.Bundle
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Calculate
import androidx.compose.material.icons.filled.Compare
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.core.view.WindowCompat
import androidx.window.core.layout.WindowSizeClass
import com.eftcalculator.data.AmmoEntity
import org.json.JSONObject
import java.util.Locale
import kotlin.math.roundToInt

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightStatusBars =
            resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK != Configuration.UI_MODE_NIGHT_YES
        setContent { EftCalculatorApp() }
    }
}

private fun text(en: String, zh: String) = if (Locale.getDefault().language.startsWith("zh")) zh else en
private fun number(value: Double) = String.format(Locale.ROOT, "%.1f", value)
private fun percent(value: Double) = number(value * 100) + "%"
private fun AmmoEntity.displayName() = if (Locale.getDefault().language.startsWith("zh")) nameZh ?: name else name
private fun materialName(value: String) = text(value, mapOf("ceramic" to "陶瓷", "steel" to "装甲钢", "aramid" to "芳纶", "uhmwpe" to "超高分子量聚乙烯", "titanium" to "钛", "combined" to "复合材料", "aluminum" to "铝", "glass" to "防弹玻璃")[value] ?: value)
private fun warningText(value: String) = text(value, mapOf(
    "Stomach: no death prediction; black-limb overflow is not modeled." to "腹部不预测致死；尚未模拟黑肢伤害扩散。",
    "Distance decay is a linear sensitivity estimate, NOT verified EFT flight physics." to "距离衰减为线性敏感性估算，尚未经游戏弹道验证。",
    "Distance decay disabled: calculations use muzzle damage/penetration." to "距离衰减已关闭，当前使用枪口处的伤害与穿深。",
    "Backing-soft-armor blunt attenuation is not modeled; blunt damage is approximate." to "尚未模拟后方软甲对钝伤的衰减，钝伤数值为近似值。",
    "All pellets hit this same chosen armor path; no spread or partial-hit selection." to "全部弹丸命中所选护甲路径，未模拟散布或部分命中。"
)[value] ?: value)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EftCalculatorApp(vm: MainViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val ammo by vm.ammo.collectAsState()
    val favorites by vm.favorites.collectAsState()
    var destination by rememberSaveable { mutableIntStateOf(0) }
    var search by rememberSaveable { mutableStateOf(false) }
    var armor by rememberSaveable { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    var dataInfo by remember { mutableStateOf(false) }
    val wide = currentWindowAdaptiveInfo().windowSizeClass
        .isWidthAtLeastBreakpoint(WindowSizeClass.WIDTH_DP_EXPANDED_LOWER_BOUND)
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme(primary = Color(0xFFF0C36A), surface = Color(0xFF171C21)) else lightColorScheme(primary = Color(0xFF775A18))) {
        Scaffold(topBar = {
            TopAppBar(title = { Text("EFT Calculator", fontWeight = FontWeight.Bold) }, actions = {
                IconButton(onClick = { search = true }) { Icon(Icons.Default.Search, stringResource(R.string.search)) }
                IconButton(onClick = { menu = true }) { Icon(Icons.Default.MoreVert, stringResource(R.string.menu)) }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text(stringResource(R.string.sync_data)) }, onClick = { vm.syncNow(); menu = false; dataInfo = true })
                    DropdownMenuItem(text = { Text(stringResource(R.string.settings_data)) }, onClick = { dataInfo = true; menu = false })
                }
            })
        }, bottomBar = {
            NavigationBar {
                listOf(Triple(R.string.nav_quick, Icons.Default.Calculate, 0), Triple(R.string.nav_compare, Icons.Default.Compare, 1),
                    Triple(R.string.nav_favorites, Icons.Default.Favorite, 2)).forEach { (label, icon, index) ->
                    NavigationBarItem(selected = destination == index, onClick = { destination = index },
                        icon = { Icon(icon, stringResource(label)) }, label = { Text(stringResource(label)) })
                }
            }
        }) { padding ->
            if (destination == 0) {
                if (wide) Row(Modifier.padding(padding).fillMaxSize().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column(Modifier.weight(0.42f).fillMaxHeight().verticalScroll(rememberScrollState())) {
                        Inputs(state, vm, { search = true }, { armor = true })
                    }
                    Column(Modifier.weight(0.58f).fillMaxHeight().verticalScroll(rememberScrollState())) { Results(state, vm::simulate) }
                } else LazyColumn(Modifier.padding(padding).fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item {
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(12.dp)) {
                                Text(text("First-trigger penetration · expected total damage", "首发穿透率 · 首发期望总伤害"), fontSize = 12.sp)
                                Text(state.result?.let { "${percent(it.penetration)} · ${number(it.healthDamage + it.bluntDamage)}" } ?: "—",
                                    style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                    item { Inputs(state, vm, { search = true }, { armor = true }) }
                    item { Results(state, vm::simulate) }
                }
            } else LazyColumn(Modifier.padding(padding).fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Text(if (destination == 1) text("Ammo data comparison (not penetration probabilities)", "\u5f39\u836f\u6570\u636e\u5bf9\u6bd4\uff08\u975e\u7a7f\u900f\u6982\u7387\uff09") else stringResource(R.string.nav_favorites)) }
                items(if (destination == 1) ammo else favorites, key = { it.id }) { item ->
                    AmmoRow(item) { vm.selectAmmo(item); destination = 0 }
                }
            }
        }
        if (search) AmmoPicker(ammo, vm.query.value, { vm.query.value = it }, { vm.selectAmmo(it); search = false }, { search = false })
        if (armor) ArmorEditor(state.armor, vm, { armor = false })
        if (dataInfo) AlertDialog(onDismissRequest = { dataInfo = false }, confirmButton = { TextButton(onClick = { dataInfo = false }) { Text(text("Close", "关闭")) } },
            title = { Text(stringResource(R.string.settings_data)) }, text = { Text(text(
                "Item identities reviewed 2026-10-25. Three source conflicts remain documented; damage/wear values were retained. Live sync retains offline data on failure. Exact item-ID icons. Community armor model. See docs/AUDIT_2026-10-25.md.",
                "物品身份核对日期：2026-10-25。已记录三项来源冲突，未擅自覆盖伤害等数值。同步失败保留离线数据。图片按物品 ID 绑定。护甲模型为社区近似，未证实与当前服务器完全一致。详见 docs/AUDIT_2026-10-25.md。")) })
    }
}

@Composable
private fun Inputs(state: CalculatorState, vm: MainViewModel, onSearch: () -> Unit, onArmor: () -> Unit) {
    var advanced by rememberSaveable { mutableStateOf(false) }
    val context = LocalContext.current
    val armorCatalog = remember { loadArmor(context) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.query_parameters), style = MaterialTheme.typography.titleLarge)
            Button(onClick = onSearch, modifier = Modifier.fillMaxWidth()) { Text(state.selectedAmmo?.let { "${it.shortName} | ${it.caliber}" } ?: stringResource(R.string.choose_ammo)) }
            state.selectedAmmo?.let { item ->
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ItemIcon(item.id.removePrefix("custom-"), "ammo", item.name)
                    Text(item.displayName(), modifier = Modifier.weight(1f))
                }
                Text(text("Damage ${number(item.damage)} | Pen ${number(item.penetrationPower)} | Armor damage ${number(item.armorDamagePercent)}%", "伤害 ${number(item.damage)} | 穿深 ${number(item.penetrationPower)} | 甲伤 ${number(item.armorDamagePercent)}%"))
                if (item.projectileCount > 1) Text(text("${item.projectileCount} projectiles per trigger; ALL hit the same path.", "每发 ${item.projectileCount} 颗弹丸，全部命中同一路径。"), fontSize = 12.sp)
            }
            Button(onClick = onArmor, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.armor_layers) + " (${state.armor.size})") }
            state.armor.forEachIndexed { i, layer ->
                val known = armorCatalog.firstOrNull { it.id == layer.itemId }
                val label = if (known != null && layer.name in listOf(known.nameEn, known.nameZh, "SAPI level III+ ballistic plate")) text(known.nameEn, known.nameZh) else layer.name
                if (i > 0) Text("↓", color = MaterialTheme.colorScheme.primary)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ItemIcon(layer.itemId, "armor", layer.name)
                    Column(Modifier.weight(1f)) {
                        Text("${i + 1}. ${if (layer.enabled) "" else text("[Disabled] ", "[已停用] ")}$label", fontWeight = FontWeight.Bold)
                        Text(text("Class ${layer.armorClass}", "${layer.armorClass} 级") + " | ${materialName(layer.material)} | ${number(layer.durability.toDouble())}/${number(layer.repairedMaximum.toDouble())} " + text("(original ${number(layer.maximum.toDouble())})", "（出厂 ${number(layer.maximum.toDouble())}）"), fontSize = 12.sp)
                    }
                }
            }
            Text(stringResource(R.string.burst_value, state.shots))
            Slider(value = state.shots.toFloat(), onValueChange = { vm.updateConditions(shots = it.roundToInt().coerceIn(1, 20)) }, valueRange = 1f..20f, steps = 18)
            TextButton(onClick = { advanced = !advanced }) { Text(if (advanced) text("Hide advanced settings", "收起专业参数") else text("Body part, distance and reset settings", "命中部位、距离与重置设置")) }
            if (advanced) {
            TextButton(onClick = vm::toggleFavorite, enabled = state.selectedAmmo != null) { Text(stringResource(R.string.toggle_favorite)) }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TextButton(onClick = vm::resetAmmo) { Text(stringResource(R.string.reset_ammo)) }
                TextButton(onClick = vm::resetArmor) { Text(stringResource(R.string.reset_armor)) }
                TextButton(onClick = vm::resetAll) { Text(stringResource(R.string.reset_all)) }
            }
            Selector(text("Body part", "\u547d\u4e2d\u90e8\u4f4d"), state.bodyPart,
                listOf("thorax" to text("Thorax (85 HP)", "\u80f8\u90e8 (85 HP)"), "head" to text("Head (35 HP)", "\u5934\u90e8 (35 HP)"), "stomach" to text("Stomach (no kill prediction)", "\u8179\u90e8\uff08\u4e0d\u9884\u6d4b\u81f4\u6b7b\uff09"))) { vm.updatePhysics(bodyPart = it) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = state.distanceDecay, onCheckedChange = { vm.updatePhysics(distanceDecay = it) })
                Text(text("Experimental distance decay (unverified)", "\u5b9e\u9a8c\u6027\u8ddd\u79bb\u8870\u51cf\uff08\u672a\u5b9e\u6d4b\uff09"))
            }
            Text(stringResource(R.string.distance_value, state.distance))
            Slider(value = state.distance.toFloat(), onValueChange = { vm.updateConditions(distance = it.roundToInt()) }, valueRange = 0f..1000f, enabled = state.distanceDecay)
            }
        }
    }
}

@Composable
private fun Results(state: CalculatorState, onSimulate: () -> Unit) {
    val r = state.result
    var details by rememberSaveable { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.first_shot_all_armor))
            Text(r?.let { percent(it.penetration) } ?: "\u2014", fontSize = 48.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            if (state.calculating) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (r == null) Text(if (state.calculating) stringResource(R.string.calculating) else stringResource(R.string.choose_ammo_auto))
            else {
                Text(text("First-trigger expected flesh / blunt damage", "\u9996\u53d1\u671f\u671b\u8089\u4f24 / \u949d\u4f24") + ": ${number(r.healthDamage)} / ${number(r.bluntDamage)}")
                Text(text("Flesh damage conditional on penetration (all penetrating pellets)", "\u6210\u529f\u7a7f\u900f\u65f6\u7684\u8089\u4f24\u5408\u8ba1\uff08\u542b\u5168\u90e8\u7a7f\u900f\u5f39\u4e38\uff09") + ": ${r.conditionalDamage?.let(::number) ?: "—"}")
                Text(text("At least one penetration in first ${minOf(3, state.shots)} triggers", "\u524d ${minOf(3, state.shots)} \u53d1\u81f3\u5c11\u4e00\u6b21\u7a7f\u900f") + ": ${percent(r.threeShot)}")
                Text(text("Entire burst expected damage", "\u6574\u8f6e\u603b\u4f24\u5bb3\u671f\u671b") + ": ${number(r.burstDamage)}")
                Text(if (r.samples == 0) text("Exact single-projectile expectation", "\u5355\u5f39\u4e38\u89e3\u6790\u671f\u671b") else text("${r.samples} samples; 95% CI ${percent(r.intervalLow)} - ${percent(r.intervalHigh)}", "抽样 ${r.samples} 次；95% 置信区间 ${percent(r.intervalLow)} - ${percent(r.intervalHigh)}"))
                Text(text("Community model uncertainty is NOT included in the sampling interval.", "\u62bd\u6837\u533a\u95f4\u4e0d\u5305\u542b\u6e38\u620f\u6a21\u578b\u7684\u4e0d\u786e\u5b9a\u6027\u3002"), fontSize = 12.sp)
                TextButton(onClick = { details = !details }) { Text(if (details) text("Hide detailed charts and layers", "收起图表与分层详情") else text("Show charts and layer details", "展开图表与分层详情")) }
                if (details) {
                Text("${r.rulesetVersion}\n${r.dataVersion}", fontSize = 11.sp)
                Text(text("Per-trigger penetration (%)", "\u9010\u53d1\u7a7f\u900f\u6982\u7387 (%)"))
                LineChart(listOf(r.burst.map { it.penetrationPercent }), 100.0, 1)
                if (r.durability.firstOrNull()?.isNotEmpty() == true) {
                    Text(text("Armor durability (points); x=0 is before firing", "\u62a4\u7532\u8010\u4e45\uff08\u70b9\uff09\uff1b0 \u4e3a\u5c04\u51fb\u524d"))
                    val series = r.durability[0].indices.map { i -> r.durability.map { it[i] } }
                    LineChart(series, series.flatten().maxOrNull()?.coerceAtLeast(1.0) ?: 1.0, 0)
                    state.armor.filter { it.enabled }.forEachIndexed { i, a -> Text("${i + 1}. ${a.name}", fontSize = 11.sp) }
                }
                Text(text("Layer table: FIRST projectile only", "\u5206\u5c42\u8be6\u60c5\uff1a\u4ec5\u9996\u9897\u5f39\u4e38"), fontWeight = FontWeight.Bold)
                r.layers.forEach { Text("${it.name}: ${number(it.penetrationPercent)}% | ${number(it.durabilityAfter)}", fontSize = 12.sp) }
                Text(text("Trigger | penetration | cumulative kill probability", "\u53d1\u6570 | \u7a7f\u900f | \u7d2f\u8ba1\u81f4\u6b7b\u6982\u7387"), fontWeight = FontWeight.Bold)
                r.burst.forEach { Text("${it.shot} | ${number(it.penetrationPercent)}% | ${it.killPercent?.let { v -> number(v) + "%" } ?: text("Not modeled", "未建模")}", fontSize = 12.sp) }
                }
                r.warnings.forEach { Text(warningText(it), fontSize = 11.sp) }
            }
            Button(onClick = onSimulate, enabled = !state.calculating && state.selectedAmmo != null) { Text(stringResource(R.string.run_monte_carlo)) }
        }
    }
}

@Composable
private fun LineChart(series: List<List<Double>>, maxY: Double, firstX: Int) {
    val colors = listOf(MaterialTheme.colorScheme.primary, Color(0xFF82C690), Color(0xFF7AAEDD), Color(0xFFDB91C6))
    Column {
        Text("0 - ${number(maxY)}", fontSize = 11.sp)
        Canvas(Modifier.fillMaxWidth().height(130.dp)) {
            drawLine(Color.Gray, Offset(0f, size.height), Offset(size.width, size.height), 1f)
            drawLine(Color.Gray, Offset.Zero, Offset(0f, size.height), 1f)
            series.forEachIndexed { n, values ->
                val points = values.mapIndexed { i, value -> Offset(size.width * i / maxOf(1, values.size - 1), size.height * (1 - value.coerceIn(0.0, maxY) / maxY).toFloat()) }
                points.zipWithNext().forEach { (a, b) -> drawLine(colors[n % colors.size], a, b, 3f) }
                points.forEach { drawCircle(colors[n % colors.size], 3f, it) }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(firstX.toString(), fontSize = 11.sp); Text(((series.firstOrNull()?.size ?: 1) - 1 + firstX).toString(), fontSize = 11.sp) }
    }
}

@Composable
private fun ItemIcon(id: String, kind: String, description: String) {
    val context = LocalContext.current
    val bitmap = remember(id, kind) { runCatching { context.assets.open("$kind-live/$id.webp").use(BitmapFactory::decodeStream) }.getOrNull() }
    if (bitmap != null) Image(bitmap.asImageBitmap(), description, Modifier.size(46.dp))
    else Icon(Icons.Default.HelpOutline, text("No verified item image", "\u65e0\u5df2\u6838\u5bf9\u56fe\u6807"), Modifier.size(40.dp))
}

@Composable
private fun AmmoRow(item: AmmoEntity, onSelect: () -> Unit) {
    OutlinedButton(onClick = onSelect, modifier = Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ItemIcon(item.id, "ammo", item.name)
            Column(Modifier.weight(1f)) {
                Text(item.displayName())
                Text("${displayCaliber(item.caliber)} | " + text("DMG", "伤害") + " ${number(item.damage)} | " + text("PEN", "穿深") + " ${number(item.penetrationPower)} | " + text("AD", "甲伤") + " ${number(item.armorDamagePercent)}% | ×${item.projectileCount}", fontSize = 11.sp)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AmmoPicker(ammo: List<AmmoEntity>, query: String, onQuery: (String) -> Unit, onSelect: (AmmoEntity) -> Unit, onDismiss: () -> Unit) {
    var caliber by remember { mutableStateOf("") }
    val calibers = ammo.map { displayCaliber(it.caliber) }.distinct().sorted()
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().fillMaxHeight(0.9f).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.choose_ammo), style = MaterialTheme.typography.titleLarge)
            TextField(value = query, onValueChange = onQuery, label = { Text(stringResource(R.string.search)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Selector(text("Caliber", "\u53e3\u5f84"), caliber, listOf("" to text("All calibers", "\u5168\u90e8\u53e3\u5f84")) + calibers.map { it to it }) { caliber = it }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(ammo.filter { caliberMatches(it.caliber, caliber) }, key = { it.id }) { AmmoRow(it) { onSelect(it) } }
            }
        }
    }
}

private fun loadArmor(context: Context): List<ArmorPlatePreset> = runCatching {
    val root = JSONObject(context.assets.open("catalog.json").bufferedReader().use { it.readText() })
    val array = root.getJSONArray("armor")
    (0 until array.length()).map { i ->
        val o = array.getJSONObject(i)
        val zones = o.getJSONArray("slots")
        ArmorPlatePreset(o.getString("id"), o.getString("name"), o.getString("name_zh"), o.getInt("armor_class"),
            o.getDouble("durability").toFloat(), o.getString("material"), (0 until zones.length()).map { zones.getString(it) }.toSet())
    }
}.getOrElse { armorPlatePresets }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArmorEditor(layers: List<ArmorInput>, vm: MainViewModel, onDismiss: () -> Unit) {
    var index by remember { mutableIntStateOf(0) }
    val selected = index.coerceIn(0, maxOf(0, layers.lastIndex))
    val current = layers.getOrNull(selected) ?: ArmorInput()
    val context = LocalContext.current
    val catalog = remember { loadArmor(context) }
    var armorClass by remember(current) { mutableIntStateOf(current.armorClass) }
    var material by remember(current) { mutableStateOf(current.material) }
    var layerType by remember(current) { mutableStateOf(current.layerType) }
    var enabled by remember(current) { mutableStateOf(current.enabled) }
    var name by remember(current) { mutableStateOf(current.name) }
    var original by remember(current) { mutableStateOf(number(current.maximum.toDouble())) }
    var repaired by remember(current) { mutableStateOf(number(current.repairedMaximum.toDouble())) }
    var durability by remember(current) { mutableStateOf(number(current.durability.toDouble())) }
    var throughput by remember(current) { mutableStateOf(number(current.bluntThroughput * 100)) }
    var presetId by remember(current) { mutableStateOf(current.itemId) }
    var filterClass by remember { mutableStateOf("") }
    var filterMaterial by remember { mutableStateOf("") }
    val materials = listOf("aramid", "uhmwpe", "combined", "titanium", "aluminum", "steel", "ceramic", "glass")
    val o = original.toFloatOrNull()?.takeIf { it.isFinite() && it > 0f && it <= 10000f }
    val r = repaired.toFloatOrNull()?.takeIf { it.isFinite() && it > 0f && o != null && it <= o }
    val d = durability.toFloatOrNull()?.takeIf { it.isFinite() && it >= 0f && r != null && it <= r }
    val b = throughput.toDoubleOrNull()?.takeIf { it.isFinite() && it in 0.0..100.0 }
    val valid = o != null && r != null && d != null && b != null && name.isNotBlank()
    fun value() = ArmorInput(armorClass = armorClass, material = material, durability = d!!, maximum = o!!,
        repairedMaximum = r!!, name = name, layerType = layerType, bluntThroughput = b!! / 100, enabled = enabled, itemId = presetId)
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().fillMaxHeight(0.94f).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.armor_layers), style = MaterialTheme.typography.titleLarge)
            Text(text("Order is outside to body. Separate front/back plates are NOT stacked automatically.", "\u7531\u5916\u5411\u5185\u6392\u5217\u3002\u524d\u540e\u63d2\u677f\u4e0d\u4f1a\u81ea\u52a8\u53e0\u52a0\u4e3a\u540c\u4e00\u547d\u4e2d\u8def\u5f84\u3002"))
            if (layers.isNotEmpty()) Selector(text("Edit layer", "\u7f16\u8f91\u5f53\u524d\u5c42"), selected.toString(), layers.mapIndexed { i, a -> i.toString() to "${i + 1}. ${a.name}" }) { index = it.toInt() }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = { vm.moveArmor(selected, -1); index = (selected - 1).coerceAtLeast(0) }, enabled = selected > 0) { Text(text("Outward", "\u4e0a\u79fb")) }
                TextButton(onClick = { vm.moveArmor(selected, 1); index = (selected + 1).coerceAtMost(layers.lastIndex) }, enabled = selected < layers.lastIndex) { Text(text("Inward", "\u4e0b\u79fb")) }
                TextButton(onClick = { vm.removeArmor(selected); index = 0 }, enabled = layers.isNotEmpty()) { Text(text("Remove", "\u5220\u9664")) }
            }
            Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(enabled, { enabled = it }); Text(text("Layer enabled", "\u542f\u7528\u6b64\u5c42")) }
            Selector(text("Preset class filter", "\u9884\u8bbe\u7b5b\u9009\uff1a\u7b49\u7ea7"), filterClass, listOf("" to text("All", "全部")) + (1..6).map { it.toString() to it.toString() }) { filterClass = it }
            Selector(text("Preset material filter", "\u9884\u8bbe\u7b5b\u9009\uff1a\u6750\u8d28"), filterMaterial, listOf("" to text("All", "全部")) + materials.map { it to materialName(it) }) { filterMaterial = it }
            val options = catalog.filter { (filterClass.isEmpty() || it.armorClass.toString() == filterClass) && (filterMaterial.isEmpty() || it.material == filterMaterial) }
            Selector(text("Verified plate presets", "\u5df2\u6838\u5bf9\u63d2\u677f\u9884\u8bbe"), presetId, listOf("" to text("Custom / select", "\u81ea\u5b9a\u4e49 / \u9009\u62e9")) + options.map { it.id to "${text(it.nameEn, it.nameZh)} | ${it.armorClass} | ${materialName(it.material)} | ${it.durability}" }) { id ->
                presetId = id
                catalog.firstOrNull { it.id == id }?.let { p ->
                    armorClass = p.armorClass; material = p.material; name = text(p.nameEn, p.nameZh)
                    original = number(p.durability.toDouble()); repaired = original; durability = original; layerType = "plate"
                }
            }
            if (presetId.isNotEmpty()) ItemIcon(presetId, "armor", name)
            TextField(name, { name = it }, label = { Text(stringResource(R.string.layer_name)) }, modifier = Modifier.fillMaxWidth())
            Selector(text("Layer type", "\u9632\u62a4\u5c42\u7c7b\u578b"), layerType, listOf("plate" to text("Plate", "插板"), "soft" to text("Soft armor", "软甲"), "helmet" to text("Helmet (no ricochet)", "头盔（不模拟跳弹）"))) { layerType = it; presetId = "" }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(5.dp)) { (1..6).forEach { n -> FilterChip(selected = armorClass == n, onClick = { armorClass = n; presetId = ""; name = text("Custom armor", "\u81ea\u5b9a\u4e49\u62a4\u7532") }, label = { Text(n.toString()) }) } }
            Selector(text("Material", "\u6750\u8d28"), material, materials.map { it to materialName(it) }) { material = it; presetId = ""; name = text("Custom armor", "\u81ea\u5b9a\u4e49\u62a4\u7532") }
            TextField(original, { original = it }, label = { Text(stringResource(R.string.original_durability)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            TextField(repaired, { repaired = it }, label = { Text(text("Repaired maximum", "\u4fee\u540e\u8010\u4e45\u4e0a\u9650")) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            TextField(durability, { durability = it }, label = { Text(stringResource(R.string.current_durability)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            if (r != null && r > 0 && d != null) Slider(d, { durability = number(it.toDouble()) }, valueRange = 0f..r)
            if (d != null && o != null) Text(text("Effective durability uses current / original", "\u6709\u6548\u8010\u4e45\u6bd4\u4f8b = \u5f53\u524d / \u539f\u5382") + ": ${percent((d / o).toDouble())}")
            TextField(throughput, { throughput = it }, label = { Text(text("Blunt throughput (%) - item-specific", "\u949d\u4f24\u4f20\u9012 (%) - \u6309\u7269\u54c1\u586b\u5199")) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            if (!valid) Text(text("Required: 0 <= current <= repaired <= original; throughput 0-100%.", "\u9700\u8981\uff1a0 <= \u5f53\u524d <= \u4fee\u540e <= \u539f\u5382\uff1b\u949d\u4f24 0-100%\u3002"), color = MaterialTheme.colorScheme.error)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.updateArmor(selected, value()); onDismiss() }, enabled = valid && layers.isNotEmpty()) { Text(stringResource(R.string.update_current_layer)) }
                Button(onClick = { vm.addArmor(value()); onDismiss() }, enabled = valid && layers.size < 12) { Text(stringResource(R.string.append_next_layer)) }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Selector(label: String, value: String, options: List<Pair<String, String>>, onSelect: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) { Text("$label: ${options.firstOrNull { it.first == value }?.second ?: value}") }
        DropdownMenu(open, { open = false }, modifier = Modifier.heightIn(max = 360.dp)) {
            options.forEach { (id, title) -> DropdownMenuItem(text = { Text(title) }, onClick = { open = false; onSelect(id) }) }
        }
    }
}
