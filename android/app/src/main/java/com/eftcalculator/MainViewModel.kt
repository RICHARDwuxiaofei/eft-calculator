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
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import androidx.room.withTransaction

data class ArmorInput(
    val armorClass: Int = 5,
    val material: String = "ceramic",
    val durability: Float = 50f,
    val maximum: Float = 50f,
    val name: String = "SAPI level III+ ballistic plate",
    val carrierId: String = "free",
    val slot: String = "front",
    val repairedMaximum: Float = maximum,
    val layerType: String = "plate",
    val bluntThroughput: Double = 0.1,
    val enabled: Boolean = true,
    val itemId: String = "655746010177119f4a097ff7",
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
    val bodyPart: String = "thorax",
    val distanceDecay: Boolean = false,
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
    private var calculation: Job? = null
    private var generation = 0L
    private val engineMutex = Mutex()

    init {
        viewModelScope.launch {
            val dao = database.ammoDao()
            val existing = dao.all().associateBy { it.id }
            val bundled = bundledAmmo()
            val syncedAt = preferences.lastSync.first()
            // Only replace the old shipped snapshot, never a newer/user-imported one.
            val install = bundled.filter { item ->
                existing[item.id]?.source.let { source -> source == null || source == "bundled" ||
                    source == "TarkovTracker/tarkovdata" ||
                    (source == "tarkov.dev" && syncedAt < 1789516800000L) }
            }
            database.withTransaction {
                dao.upsertAll(install)
                bundled.forEach { item ->
                    legacyId(item)?.let { old ->
                        if (dao.isFavorite(old)) dao.addFavorite(com.eftcalculator.data.FavoriteEntity(item.id))
                        dao.deleteAmmo(old)
                    }
                }
            }
        }
        DataSyncWorker.schedule(application)
    }

    private fun legacyId(item: AmmoEntity): String? = when {
        item.caliber == "5.56x45" && item.shortName.equals("M855A1", true) -> "m855a1"
        item.caliber == "5.56x45" && item.shortName.equals("M855", true) -> "m855"
        item.caliber == "5.56x45" && item.shortName.equals("M995", true) -> "m995"
        item.shortName.equals("M80", true) -> "m80"
        item.shortName.equals("7N40", true) -> "7n40"
        item.name.contains("AP-20", true) -> "ap20"
        item.name.contains("Magnum buckshot", true) -> "buckshot"
        item.name.contains("7.62x39") && item.name.contains("BP") -> "762bp"
        item.name.contains("5.45x39") && item.name.contains("BP") -> "545bp"
        else -> null
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
        require(damage.isFinite() && damage >= 0 && penetration.isFinite() && penetration >= 0)
        require(armorDamage.isFinite() && armorDamage in 0.0..100.0 && projectileCount in 1..64)
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
        if (index !in _state.value.armor.indices) return
        require(value.durability.isFinite() && value.repairedMaximum.isFinite() && value.maximum.isFinite())
        require(value.durability >= 0f && value.durability <= value.repairedMaximum &&
            value.repairedMaximum <= value.maximum && value.maximum > 0f)
        val armor = _state.value.armor.toMutableList()
        armor[index] = value
        _state.value = _state.value.copy(armor = armor)
        calculate()
    }

    fun addArmor(value: ArmorInput) {
        if (_state.value.armor.size >= 12) return
        _state.value = _state.value.copy(armor = _state.value.armor + value)
        calculate()
    }

    fun removeArmor(index: Int) {
        _state.value = _state.value.copy(armor = _state.value.armor.filterIndexed { i, _ -> i != index })
        calculate()
    }

    fun moveArmor(index: Int, direction: Int) {
        val list = _state.value.armor.toMutableList()
        val target = index + direction
        if (index !in list.indices || target !in list.indices) return
        val value = list.removeAt(index)
        list.add(target, value)
        _state.value = _state.value.copy(armor = list)
        calculate()
    }

    fun updatePhysics(bodyPart: String = _state.value.bodyPart, distanceDecay: Boolean = _state.value.distanceDecay) {
        require(bodyPart in listOf("head", "thorax", "stomach"))
        _state.value = _state.value.copy(bodyPart = bodyPart, distanceDecay = distanceDecay)
        calculate()
    }

    fun resetArmor() {
        _state.value = _state.value.copy(armor = listOf(ArmorInput()))
        calculate()
    }

    fun resetAmmo() {
        viewModelScope.launch {
            val default = database.ammoDao().all().firstOrNull {
                it.id == "54527ac44bdc2d36668b4567"
            } ?: database.ammoDao().all().firstOrNull()
            if (default != null) selectAmmo(default)
        }
    }

    fun resetAll() {
        _state.value = _state.value.copy(
            armor = listOf(ArmorInput()),
            distance = 0,
            shots = 3,
            bodyPart = "thorax",
            distanceDecay = false,
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

    fun calculate() = startCalculation(false)

    fun simulate() = startCalculation(true)

    private fun startCalculation(simulated: Boolean) {
        val revision = ++generation
        calculation?.cancel()
        val snapshot = _state.value
        val selected = snapshot.selectedAmmo
        _state.value = snapshot.copy(result = null, calculating = selected != null, error = null)
        if (selected == null) return
        calculation = viewModelScope.launch {
            try {
                if (!simulated) delay(150)
                val value = engineMutex.withLock {
                    val input = scenarioJson(selected, snapshot, if (simulated) 10000 else 2048)
                    if (simulated) engine.simulate(input) else engine.calculate(input)
                }
                if (revision == generation) _state.value = _state.value.copy(result = value, calculating = false)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (revision == generation) _state.value = _state.value.copy(error = error.message, calculating = false)
            }
        }
    }

    private fun scenarioJson(ammo: AmmoEntity, state: CalculatorState, iterations: Int): String {
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
            .put("muzzle_velocity", ammo.initialSpeed)
        val layers = JSONArray()
        state.armor.forEachIndexed { index, armor ->
            layers.put(
                JSONObject()
                    .put("id", "android-$index")
                    .put("name", armor.name.ifBlank { "Armor layer ${index + 1}" })
                    .put("layer_type", armor.layerType)
                    .put("armor_class", armor.armorClass)
                    .put("current_durability", armor.durability)
                    .put("displayed_max_durability", armor.repairedMaximum)
                    .put("original_max_durability", armor.maximum)
                    .put("material", armor.material)
                    .put("destructibility", destructibility(armor.material))
                    .put("blunt_throughput", armor.bluntThroughput)
                    .put("enabled", armor.enabled)
                    .put("is_hard_armor", armor.layerType != "soft"),
            )
        }
        return JSONObject()
            .put("schema_version", 1)
            .put("ammo", ammoJson)
            .put("armor_layers", layers)
            .put("distance_m", state.distance)
            .put("shot_count", state.shots)
            .put("body_part", state.bodyPart)
            .put("enable_distance_decay", state.distanceDecay)
            .put("simulation_iterations", iterations)
            .put("random_seed", 20260916)
            .toString()
    }

    private fun destructibility(material: String) = when (material) {
        "steel" -> 0.525
        "uhmwpe" -> 0.3375
        "aramid" -> 0.1875
        "titanium" -> 0.4125
        "combined" -> 0.375
        "aluminum" -> 0.45
        "ceramic", "glass" -> 0.6
        else -> error("Unknown armor material: $material")
    }

    private fun bundledAmmo(): List<AmmoEntity> {
        val raw = getApplication<Application>().assets.open("catalog.json").bufferedReader().use { it.readText() }
        val root = JSONObject(raw)
        val items = root.getJSONArray("ammo")
        return (0 until items.length()).map { i ->
            val item = items.getJSONObject(i)
            val name = item.getString("name")
            val short = item.getString("short_name")
            val zh = item.optJSONObject("localized_names")?.optString("zh")
            val caliber = item.getString("caliber")
            AmmoEntity(item.getString("id"), name, short, caliber,
                item.getDouble("damage"), item.getDouble("penetration_power"),
                item.getDouble("armor_damage_percent"), item.getInt("projectile_count"),
                item.optDouble("muzzle_velocity").takeIf { it.isFinite() },
                root.getString("version"), "$name $short $caliber ${zh.orEmpty()}", zh)
        }
    }
}
