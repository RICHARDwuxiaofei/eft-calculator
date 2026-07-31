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
    val durability: Float = 45f,
    val maximum: Float = 45f,
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
                    .put("name", "Armor layer ${index + 1}")
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
        AmmoEntity("m855a1", "5.56x45mm M855A1", "M855A1", "5.56x45", 47.0, 40.0, 52.0, 1, 945.0, "bundled", "5.56x45mm M855A1 M855A1 5.56x45"),
        AmmoEntity("m855", "5.56x45mm M855", "M855", "5.56x45", 53.0, 31.0, 37.0, 1, 922.0, "bundled", "5.56x45mm M855 M855 5.56x45"),
        AmmoEntity("m995", "5.56x45mm M995", "M995", "5.56x45", 42.0, 53.0, 58.0, 1, 1013.0, "bundled", "5.56x45mm M995 M995 5.56x45"),
        AmmoEntity("762bp", "7.62x39mm BP gzh", "BP", "7.62x39", 58.0, 47.0, 63.0, 1, 730.0, "bundled", "7.62x39mm BP gzh BP 7.62x39"),
        AmmoEntity("7n40", "5.45x39mm 7N40", "7N40", "5.45x39", 52.0, 42.0, 50.0, 1, 915.0, "bundled", "5.45x39mm 7N40 5.45x39"),
        AmmoEntity("545bp", "5.45x39mm BP gs", "BP", "5.45x39", 48.0, 45.0, 48.0, 1, 890.0, "bundled", "5.45x39mm BP gs BP 5.45x39"),
        AmmoEntity("m80", "7.62x51mm M80", "M80", "7.62x51", 80.0, 41.0, 66.0, 1, 833.0, "bundled", "7.62x51mm M80 7.62x51"),
        AmmoEntity("ap20", "12/70 AP-20", "AP-20", "12/70", 164.0, 37.0, 65.0, 1, 510.0, "bundled", "12/70 AP-20"),
        AmmoEntity("buckshot", "12/70 Magnum buckshot", "Magnum", "12/70", 50.0, 2.0, 26.0, 8, 385.0, "bundled", "12/70 Magnum buckshot"),
    )
}
