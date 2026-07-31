package com.eftcalculator

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.eftcalculator.data.AmmoEntity
import com.eftcalculator.data.AppDatabase
import com.eftcalculator.data.DataSyncWorker
import com.eftcalculator.data.PreferencesRepository
import com.eftcalculator.engine.PythonSimulationEngine
import com.eftcalculator.engine.SimulationSummary
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import kotlinx.coroutines.ExperimentalCoroutinesApi

data class ArmorInput(
    val armorClass: Int = 5,
    val material: String = "ceramic",
    val durability: Float = 50f,
    val maximum: Float = 50f,
    val name: String = "SAPI level III+ ballistic plate",
    val carrierId: String = "free",
    val slot: String = "front",
)

data class ArmorPlatePreset(
    val id: String,
    val nameEn: String,
    val nameZh: String,
    val armorClass: Int,
    val durability: Float,
    val material: String,
    val slots: Set<String>,
)

data class ArmorCarrierPreset(
    val id: String,
    val nameEn: String,
    val nameZh: String,
    val defaults: Map<String, String>,
)

val armorPlatePresets = listOf(
    ArmorPlatePreset("tackek-replica", "Tac-Kek SAPI III+ plate (Replica)", "Tac-Kek SAPI III+ 插板（仿制）", 1, 90f, "uhmwpe", setOf("front", "back")),
    ArmorPlatePreset("zhuk-3-front", "Zhuk-3 plate (Front)", "Zhuk-3 插板（前）", 3, 40f, "uhmwpe", setOf("front")),
    ArmorPlatePreset("6b23-2-back", "6B23-2 plate (Back)", "6B23-2 插板（后）", 4, 40f, "steel", setOf("back")),
    ArmorPlatePreset("6b33-front", "6B33 plate (Front)", "6B33 插板（前）", 4, 50f, "steel", setOf("front")),
    ArmorPlatePreset("monoclete", "Monoclete level III PE plate", "Monoclete III 级 PE 插板", 4, 40f, "uhmwpe", setOf("front", "back")),
    ArmorPlatePreset("global-steel", "Global Armor Steel plate", "Global Armor 钢制插板", 4, 45f, "steel", setOf("front", "back")),
    ArmorPlatePreset("elaphros", "SPRTN Elaphros plate", "SPRTN Elaphros 插板", 4, 45f, "ceramic", setOf("front", "back")),
    ArmorPlatePreset("omega", "SPRTN Omega plate", "SPRTN Omega 插板", 4, 50f, "combined", setOf("front", "back")),
    ArmorPlatePreset("titan", "Kiba Arms Titan plate", "Kiba Arms Titan 插板", 4, 55f, "titanium", setOf("front", "back")),
    ArmorPlatePreset("korund-front", "Korund-VM plate (Front)", "Korund-VM 插板（前）", 5, 60f, "steel", setOf("front")),
    ArmorPlatePreset("korund-back", "Korund-VM plate (Back)", "Korund-VM 插板（后）", 5, 40f, "steel", setOf("back")),
    ArmorPlatePreset("gac-3s15m", "GAC 3s15m plate", "GAC 3s15m 插板", 5, 45f, "uhmwpe", setOf("front", "back")),
    ArmorPlatePreset("sapi-iii-plus", "SAPI level III+ plate", "SAPI III+ 插板", 5, 50f, "ceramic", setOf("front", "back")),
    ArmorPlatePreset("korund-side", "Korund-VM plate (Side)", "Korund-VM 插板（侧）", 5, 25f, "steel", setOf("left", "right")),
    ArmorPlatePreset("kiteco", "KITECO SC-IV SA plate", "KITECO SC-IV SA 插板", 6, 45f, "uhmwpe", setOf("front", "back")),
    ArmorPlatePreset("kiba-steel", "Kiba Arms Steel plate", "Kiba Arms 钢制插板", 6, 50f, "steel", setOf("front", "back")),
    ArmorPlatePreset("esapi-iv", "ESAPI level IV plate", "ESAPI IV 级插板", 6, 55f, "ceramic", setOf("front", "back")),
)

val armorCarrierPresets = listOf(
    ArmorCarrierPreset("free", "No carrier restriction", "不限载具（手动搭配）", mapOf("front" to "monoclete", "back" to "monoclete", "left" to "korund-side", "right" to "korund-side")),
    ArmorCarrierPreset("6b23-2", "6B23-2 body armor", "6B23-2 防弹衣", mapOf("front" to "6b33-front", "back" to "6b23-2-back")),
    ArmorCarrierPreset("bagariy", "NPP KlASS Bagariy", "NPP KlASS Bagariy 防弹胸挂", mapOf("front" to "korund-front", "back" to "korund-back", "left" to "korund-side", "right" to "korund-side")),
    ArmorCarrierPreset("slick", "LBT-6094A Slick", "LBT-6094A Slick 板甲", mapOf("front" to "kiba-steel", "back" to "kiba-steel")),
    ArmorCarrierPreset("trooper", "HighCom Trooper TFO", "HighCom Trooper TFO 防弹衣", mapOf("front" to "monoclete", "back" to "monoclete")),
)

data class CalculatorState(
    val selectedAmmo: AmmoEntity? = null,
    val armor: List<ArmorInput> = listOf(ArmorInput()),
    val distance: Int = 0,
    val shots: Int = 3,
    val result: SimulationSummary? = null,
    val calculating: Boolean = false,
    val error: String? = null,
)

@OptIn(ExperimentalCoroutinesApi::class)
class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val database = AppDatabase.get(application)
    private val preferences = PreferencesRepository(application)
    private val engine = PythonSimulationEngine()
    val query = MutableStateFlow("")
    val ammo = query.flatMapLatest(database.ammoDao()::search)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val favorites = database.ammoDao().favorites()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val laboratoryMode = preferences.laboratoryMode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)
    val lastSync = preferences.lastSync
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0L)
    private val _state = MutableStateFlow(CalculatorState())
    val state: StateFlow<CalculatorState> = _state

    init {
        viewModelScope.launch {
            if (database.ammoDao().all().isEmpty()) {
                database.ammoDao().upsertAll(bundledAmmo())
            }
        }
        DataSyncWorker.schedule(application)
        syncNow()
    }

    fun selectAmmo(item: AmmoEntity) {
        _state.value = _state.value.copy(selectedAmmo = item)
        calculate()
    }

    fun useCustomAmmo(
        name: String,
        damage: Double,
        penetration: Double,
        armorDamage: Double,
        projectileCount: Int,
    ) {
        val base = _state.value.selectedAmmo ?: return
        selectAmmo(
            base.copy(
                id = "custom-${base.id}",
                name = name,
                shortName = name,
                damage = damage,
                penetrationPower = penetration,
                armorDamagePercent = armorDamage,
                projectileCount = projectileCount,
                source = "manual-override",
                searchText = name,
                nameZh = name,
            ),
        )
    }

    fun toggleFavorite() {
        val selected = _state.value.selectedAmmo ?: return
        viewModelScope.launch {
            if (database.ammoDao().isFavorite(selected.id)) {
                database.ammoDao().removeFavorite(selected.id)
            } else {
                database.ammoDao().addFavorite(com.eftcalculator.data.FavoriteEntity(selected.id))
            }
        }
    }

    fun updateArmor(index: Int, value: ArmorInput) {
        val armor = _state.value.armor.toMutableList()
        armor[index] = value
        _state.value = _state.value.copy(armor = armor)
        calculate()
    }

    fun addArmor(value: ArmorInput) {
        _state.value = _state.value.copy(armor = _state.value.armor + value)
        calculate()
    }

    fun resetArmor() {
        _state.value = _state.value.copy(armor = listOf(ArmorInput()))
        calculate()
    }

    fun resetAmmo() {
        viewModelScope.launch {
            val default = database.ammoDao().all().firstOrNull {
                it.shortName.equals("M855A1", ignoreCase = true)
            } ?: database.ammoDao().all().firstOrNull()
            if (default != null) selectAmmo(default)
        }
    }

    fun resetAll() {
        _state.value = _state.value.copy(
            armor = listOf(ArmorInput()),
            distance = 0,
            shots = 3,
        )
        resetAmmo()
    }

    fun updateConditions(distance: Int = _state.value.distance, shots: Int = _state.value.shots) {
        _state.value = _state.value.copy(distance = distance, shots = shots)
        calculate()
    }

    fun syncNow() {
        WorkManager.getInstance(getApplication<Application>())
            .enqueue(OneTimeWorkRequestBuilder<DataSyncWorker>().build())
    }

    fun toggleLaboratoryMode() {
        viewModelScope.launch {
            preferences.setLaboratoryMode(!laboratoryMode.value)
        }
    }

    fun calculate() {
        val snapshot = _state.value
        val selected = snapshot.selectedAmmo ?: return
        viewModelScope.launch {
            _state.value = snapshot.copy(calculating = true, error = null)
            runCatching { engine.calculate(scenarioJson(selected, snapshot)) }
                .onSuccess { _state.value = _state.value.copy(result = it, calculating = false) }
                .onFailure {
                    _state.value = _state.value.copy(error = it.message, calculating = false)
                }
        }
    }

    fun simulate() {
        val snapshot = _state.value
        val selected = snapshot.selectedAmmo ?: return
        viewModelScope.launch {
            _state.value = snapshot.copy(calculating = true, error = null)
            runCatching { engine.simulate(scenarioJson(selected, snapshot)) }
                .onSuccess { _state.value = _state.value.copy(result = it, calculating = false) }
                .onFailure {
                    _state.value = _state.value.copy(error = it.message, calculating = false)
                }
        }
    }

    private fun scenarioJson(ammo: AmmoEntity, state: CalculatorState): String {
        val ammoJson = JSONObject()
            .put("id", ammo.id)
            .put("name", ammo.name)
            .put("short_name", ammo.shortName)
            .put("caliber", ammo.caliber)
            .put("damage", ammo.damage)
            .put("penetration_power", ammo.penetrationPower)
            .put("armor_damage_percent", ammo.armorDamagePercent)
            .put("projectile_count", ammo.projectileCount)
            .put("source_version", ammo.source)
        val layers = JSONArray()
        state.armor.forEachIndexed { index, armor ->
            layers.put(
                JSONObject()
                    .put("id", "android-$index")
                    .put("name", armor.name.ifBlank { "Armor layer ${index + 1}" })
                    .put("layer_type", if (armor.material == "aramid") "soft" else "plate")
                    .put("armor_class", armor.armorClass)
                    .put("current_durability", armor.durability)
                    .put("displayed_max_durability", armor.maximum)
                    .put("original_max_durability", armor.maximum)
                    .put("material", armor.material)
                    .put("destructibility", destructibility(armor.material))
                    .put("blunt_throughput", if (armor.material == "aramid") 0.18 else 0.1)
                    .put("is_hard_armor", armor.material != "aramid"),
            )
        }
        return JSONObject()
            .put("schema_version", 1)
            .put("ammo", ammoJson)
            .put("armor_layers", layers)
            .put("distance_m", state.distance)
            .put("shot_count", state.shots)
            .put("simulation_iterations", 1_000)
            .put("random_seed", 20260731)
            .toString()
    }

    private fun destructibility(material: String) = when (material) {
        "steel" -> 0.35
        "uhmwpe" -> 0.45
        "aramid" -> 0.30
        "titanium" -> 0.42
        else -> 0.80
    }

    private fun bundledAmmo() = listOf(
        AmmoEntity("m855a1", "5.56x45mm M855A1", "M855A1", "5.56x45", 47.0, 40.0, 52.0, 1, 945.0, "bundled", "5.56x45mm M855A1 5.56x45毫米 M855A1 855a1", "5.56x45毫米 M855A1"),
        AmmoEntity("m855", "5.56x45mm M855", "M855", "5.56x45", 54.0, 31.0, 37.0, 1, 922.0, "bundled", "5.56x45mm M855 5.56x45毫米 M855 855", "5.56x45毫米 M855"),
        AmmoEntity("m995", "5.56x45mm M995", "M995", "5.56x45", 42.0, 53.0, 58.0, 1, 1013.0, "bundled", "5.56x45mm M995 5.56x45毫米 M995 995", "5.56x45毫米 M995"),
        AmmoEntity("762bp", "7.62x39mm BP gzh", "BP", "7.62x39", 58.0, 47.0, 63.0, 1, 730.0, "bundled", "7.62x39mm BP gzh 7.62x39毫米 BP gzh 762bp 7n23", "7.62x39毫米 BP gzh"),
        AmmoEntity("7n40", "5.45x39mm 7N40", "7N40", "5.45x39", 52.0, 42.0, 50.0, 1, 915.0, "bundled", "5.45x39mm 7N40 5.45x39毫米 7N40", "5.45x39毫米 7N40"),
        AmmoEntity("545bp", "5.45x39mm BP gs", "BP", "5.45x39", 48.0, 45.0, 48.0, 1, 890.0, "bundled", "5.45x39mm BP gs 5.45x39毫米 BP gs 545bp", "5.45x39毫米 BP gs"),
        AmmoEntity("m80", "7.62x51mm M80", "M80", "7.62x51", 80.0, 41.0, 66.0, 1, 833.0, "bundled", "7.62x51mm M80 7.62x51毫米 M80 308", "7.62x51毫米 M80"),
        AmmoEntity("ap20", "12/70 AP-20 armor-piercing slug", "AP-20", "12/70", 164.0, 37.0, 65.0, 1, 510.0, "bundled", "12/70 AP-20 armor-piercing slug 穿甲独头弹 ap20", "12/70 AP-20 穿甲独头弹"),
        AmmoEntity("buckshot", "12/70 8.5mm Magnum buckshot", "Magnum", "12/70", 50.0, 2.0, 26.0, 8, 385.0, "bundled", "12/70 8.5mm Magnum buckshot 马格南 鹿弹 8.5", "12/70 8.5毫米“马格南”鹿弹"),
    )
}
