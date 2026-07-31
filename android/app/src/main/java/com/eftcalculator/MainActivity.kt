package com.eftcalculator

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Calculate
import androidx.compose.material.icons.filled.Compare
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import java.text.DateFormat
import java.util.Date
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.window.core.layout.WindowSizeClass
import com.eftcalculator.data.AmmoEntity

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { EftCalculatorApp() }
    }
}

private val EftColors = darkColorScheme(
    primary = Color(0xFFC39B52),
    onPrimary = Color(0xFF101418),
    background = Color(0xFF0B0E11),
    surface = Color(0xFF171C21),
    surfaceVariant = Color(0xFF252D34),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EftCalculatorApp(vm: MainViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val ammo by vm.ammo.collectAsState()
    val favorites by vm.favorites.collectAsState()
    val laboratoryMode by vm.laboratoryMode.collectAsState()
    val lastSync by vm.lastSync.collectAsState()
    var destination by rememberSaveable { mutableIntStateOf(0) }
    var searchOpen by rememberSaveable { mutableStateOf(false) }
    var armorOpen by rememberSaveable { mutableStateOf(false) }
    var dataOpen by rememberSaveable { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    val wide = currentWindowAdaptiveInfo().windowSizeClass
        .isWidthAtLeastBreakpoint(WindowSizeClass.WIDTH_DP_MEDIUM_LOWER_BOUND)

    MaterialTheme(colorScheme = EftColors) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("EFT Calculator", fontWeight = FontWeight.Bold) },
                    actions = {
                        IconButton(onClick = { searchOpen = true }) {
                            Icon(Icons.Default.Search, stringResource(R.string.search))
                        }
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(Icons.Default.MoreVert, stringResource(R.string.menu))
                        }
                        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                            DropdownMenuItem(text = { Text(stringResource(R.string.sync_data)) }, onClick = {
                                vm.syncNow()
                                menuOpen = false
                            })
                            DropdownMenuItem(text = {
                                Text(
                                    stringResource(
                                        if (laboratoryMode) R.string.exit_laboratory
                                        else R.string.enter_laboratory,
                                    ),
                                )
                            }, onClick = {
                                vm.toggleLaboratoryMode()
                                menuOpen = false
                            })
                            DropdownMenuItem(text = { Text(stringResource(R.string.settings_data)) }, onClick = {
                                dataOpen = true
                                menuOpen = false
                            })
                        }
                    },
                )
            },
            bottomBar = {
                NavigationBar {
                    listOf(
                        Triple(stringResource(R.string.nav_quick), Icons.Default.Calculate, 0),
                        Triple(stringResource(R.string.nav_compare), Icons.Default.Compare, 1),
                        Triple(stringResource(R.string.nav_favorites), Icons.Default.Favorite, 2),
                    ).forEach { (label, icon, index) ->
                        NavigationBarItem(
                            selected = destination == index,
                            onClick = { destination = index },
                            icon = { Icon(icon, label) },
                            label = { Text(label) },
                        )
                    }
                }
            },
        ) { padding ->
            when (destination) {
                0 -> QuickScreen(
                    Modifier.padding(padding),
                    state,
                    wide,
                    onSearch = { searchOpen = true },
                    onArmor = { armorOpen = true },
                    onDistance = { vm.updateConditions(distance = it) },
                    onShots = { vm.updateConditions(shots = it) },
                    onFavorite = vm::toggleFavorite,
                    onSimulate = vm::simulate,
                )
                1 -> CompareScreen(Modifier.padding(padding), ammo, state.selectedAmmo, vm::selectAmmo)
                else -> FavoritesScreen(Modifier.padding(padding), favorites, vm::selectAmmo)
            }
        }
        if (searchOpen) {
            AmmoSearchSheet(ammo, vm.query.value, {
                vm.query.value = it
            }, {
                vm.selectAmmo(it)
                searchOpen = false
            }, { searchOpen = false })
        }
        if (armorOpen) {
            ArmorSheet(state.armor.first(), {
                vm.updateArmor(0, it)
            }, {
                vm.addArmor(it)
                armorOpen = false
            }, { armorOpen = false })
        }
        if (dataOpen) {
            DataStatusSheet(lastSync, laboratoryMode, {
                vm.syncNow()
            }, { dataOpen = false })
        }
    }
}

@Composable
private fun QuickScreen(
    modifier: Modifier,
    state: CalculatorState,
    wide: Boolean,
    onSearch: () -> Unit,
    onArmor: () -> Unit,
    onDistance: (Int) -> Unit,
    onShots: (Int) -> Unit,
    onFavorite: () -> Unit,
    onSimulate: () -> Unit,
) {
    val inputs: @Composable () -> Unit = {
        InputPane(state, onSearch, onArmor, onDistance, onShots, onFavorite)
    }
    val results: @Composable () -> Unit = { ResultPane(state, onSimulate) }
    if (wide) {
        Row(modifier.fillMaxSize().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.width(380.dp).fillMaxHeight()) { inputs() }
            Box(Modifier.weight(1f).fillMaxHeight()) { results() }
        }
    } else {
        LazyColumn(modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { inputs() }
            item { results() }
        }
    }
}

@Composable
private fun InputPane(
    state: CalculatorState,
    onSearch: () -> Unit,
    onArmor: () -> Unit,
    onDistance: (Int) -> Unit,
    onShots: (Int) -> Unit,
    onFavorite: () -> Unit,
) {
    val armorSummary = state.armor.map {
        stringResource(R.string.armor_summary, it.armorClass, materialLabel(it.material))
    }.joinToString(" → ")
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.query_parameters), fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Button(onClick = onSearch, modifier = Modifier.fillMaxWidth()) {
                Text(
                    state.selectedAmmo?.let {
                        stringResource(
                            R.string.ammo_summary,
                            it.shortName,
                            it.caliber,
                            it.damage.toInt(),
                            it.penetrationPower.toInt(),
                        )
                    } ?: stringResource(R.string.choose_ammo),
                )
            }
            TextButton(onClick = onFavorite, enabled = state.selectedAmmo != null) {
                Text(stringResource(R.string.toggle_favorite))
            }
            Button(onClick = onArmor, modifier = Modifier.fillMaxWidth()) {
                Text(armorSummary)
            }
            Text(stringResource(R.string.distance_value, state.distance))
            Slider(
                value = state.distance.toFloat(),
                onValueChange = { onDistance(it.toInt()) },
                valueRange = 0f..1000f,
            )
            Text(stringResource(R.string.burst_value, state.shots))
            Slider(
                value = state.shots.toFloat(),
                onValueChange = { onShots(it.toInt().coerceAtLeast(1)) },
                valueRange = 1f..20f,
                steps = 18,
            )
        }
    }
}

@Composable
private fun ResultPane(state: CalculatorState, onSimulate: () -> Unit) {
    val result = state.result
    Card {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.first_shot_all_armor))
            Text(
                result?.let { "${(it.penetration * 100).toInt()}%" } ?: "—",
                fontSize = 54.sp,
                fontWeight = FontWeight.Black,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                when {
                    state.calculating -> stringResource(R.string.calculating)
                    state.error != null -> state.error
                    result == null -> stringResource(R.string.choose_ammo_auto)
                    result.penetration < .15 -> stringResource(R.string.very_unlikely)
                    result.penetration < .65 -> stringResource(R.string.close_to_even)
                    else -> stringResource(R.string.likely)
                } ?: "",
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Metric(stringResource(R.string.metric_three_shots), result?.let { "${(it.threeShot * 100).toInt()}%" } ?: "—")
                Metric(stringResource(R.string.metric_health), result?.let { "%.1f".format(it.healthDamage) } ?: "—")
                Metric(stringResource(R.string.metric_blunt), result?.let { "%.1f".format(it.bluntDamage) } ?: "—")
                Metric(stringResource(R.string.metric_confidence), result?.confidence ?: "—")
            }
            Button(onClick = onSimulate, enabled = !state.calculating && state.selectedAmmo != null) {
                Text(stringResource(R.string.run_monte_carlo))
            }
            Text(stringResource(R.string.layer_details), fontWeight = FontWeight.Bold)
            result?.layers?.forEach {
                Text(
                    stringResource(
                        R.string.layer_result,
                        it.name,
                        it.penetrationPercent,
                        it.durabilityAfter,
                    ),
                    fontSize = 13.sp,
                )
            }
            Text(stringResource(R.string.burst_details), fontWeight = FontWeight.Bold)
            result?.burst?.take(10)?.forEach {
                Text(
                    stringResource(
                        R.string.burst_result,
                        it.shot,
                        it.penetrationPercent,
                        it.killPercent,
                    ),
                    fontSize = 13.sp,
                )
            }
        }
    }
}

@Composable
private fun Metric(title: String, value: String) {
    Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(12.dp).width(120.dp)) {
            Text(title, fontSize = 12.sp)
            Text(value, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun materialLabel(material: String): String = stringResource(
    when (material) {
        "steel" -> R.string.material_steel
        "uhmwpe" -> R.string.material_uhmwpe
        "aramid" -> R.string.material_aramid
        "titanium" -> R.string.material_titanium
        else -> R.string.material_ceramic
    },
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AmmoSearchSheet(
    ammo: List<AmmoEntity>,
    query: String,
    onQuery: (String) -> Unit,
    onSelect: (AmmoEntity) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            TextField(
                value = query,
                onValueChange = onQuery,
                placeholder = { Text(stringResource(R.string.search_hint)) },
                modifier = Modifier.fillMaxWidth(),
            )
            LazyColumn(Modifier.height(480.dp)) {
                items(ammo, key = { it.id }) { item ->
                    TextButton(onClick = { onSelect(item) }, modifier = Modifier.fillMaxWidth()) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("${item.shortName} · ${item.caliber}")
                            Text(
                                stringResource(
                                    R.string.ammo_damage_pen,
                                    item.damage.toInt(),
                                    item.penetrationPower.toInt(),
                                ),
                            )
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArmorSheet(
    current: ArmorInput,
    onUpdate: (ArmorInput) -> Unit,
    onAdd: (ArmorInput) -> Unit,
    onDismiss: () -> Unit,
) {
    var armorClass by remember(current) { mutableIntStateOf(current.armorClass) }
    var material by remember(current) { mutableStateOf(current.material) }
    var durability by remember(current) { mutableStateOf(current.durability) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.armor_layers), fontSize = 22.sp, fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                (1..6).forEach { value ->
                    Button(onClick = { armorClass = value }) {
                        Text(stringResource(R.string.armor_class, value))
                    }
                }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf("ceramic", "steel", "uhmwpe", "aramid", "titanium").forEach { value ->
                    Button(onClick = { material = value }) { Text(materialLabel(value)) }
                }
            }
            Text(
                stringResource(
                    R.string.durability_value,
                    durability.toInt(),
                    current.maximum.toInt(),
                ),
            )
            Slider(
                value = durability,
                onValueChange = { durability = it },
                valueRange = 0f..current.maximum,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    onUpdate(current.copy(armorClass = armorClass, material = material, durability = durability))
                    onDismiss()
                }) { Text(stringResource(R.string.update_current_layer)) }
                Button(onClick = {
                    onAdd(ArmorInput(armorClass, material, 45f, 45f))
                }) { Text(stringResource(R.string.append_next_layer)) }
            }
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun CompareScreen(
    modifier: Modifier,
    ammo: List<AmmoEntity>,
    selected: AmmoEntity?,
    onSelect: (AmmoEntity) -> Unit,
) {
    LazyColumn(modifier.fillMaxSize().padding(12.dp)) {
        item { Text(stringResource(R.string.ammo_compare), fontSize = 24.sp, fontWeight = FontWeight.Bold) }
        items(ammo, key = { it.id }) {
            TextButton(onClick = { onSelect(it) }, modifier = Modifier.fillMaxWidth()) {
                Text(
                    stringResource(
                        R.string.compare_line,
                        if (selected?.id == it.id) "✓ " else "",
                        it.shortName,
                        it.penetrationPower.toInt(),
                        it.damage.toInt(),
                    ),
                )
            }
        }
    }
}

@Composable
private fun FavoritesScreen(
    modifier: Modifier,
    ammo: List<AmmoEntity>,
    onSelect: (AmmoEntity) -> Unit,
) {
    LazyColumn(modifier.fillMaxSize().padding(16.dp)) {
        item { Text(stringResource(R.string.nav_favorites), fontSize = 24.sp, fontWeight = FontWeight.Bold) }
        if (ammo.isEmpty()) {
            item { Text(stringResource(R.string.favorites_empty)) }
        } else {
            items(ammo, key = { it.id }) {
                TextButton(onClick = { onSelect(it) }, modifier = Modifier.fillMaxWidth()) {
                    Text("${it.shortName} · ${it.caliber}")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DataStatusSheet(
    lastSync: Long,
    laboratoryMode: Boolean,
    onSync: () -> Unit,
    onDismiss: () -> Unit,
) {
    val age = System.currentTimeMillis() - lastSync
    val state = when {
        lastSync == 0L -> stringResource(R.string.never_synced)
        age > 48L * 60 * 60 * 1000 -> stringResource(R.string.data_stale)
        else -> stringResource(R.string.cache_valid)
    }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.settings_data), fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.status_value, state))
            Text(
                stringResource(
                    R.string.last_success,
                    if (lastSync == 0L) "—"
                    else DateFormat.getDateTimeInstance().format(Date(lastSync)),
                ),
            )
            Text(stringResource(R.string.source_priority))
            Text(stringResource(R.string.sync_policy))
            Text(
                stringResource(
                    R.string.current_mode,
                    stringResource(
                        if (laboratoryMode) R.string.mode_laboratory else R.string.mode_quick,
                    ),
                ),
            )
            Button(onClick = onSync) { Text(stringResource(R.string.sync_now)) }
            Spacer(Modifier.height(20.dp))
        }
    }
}
