package com.eftcalculator.engine

import com.chaquo.python.Python
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class SimulationSummary(
    val penetration: Double,
    val threeShot: Double,
    val healthDamage: Double,
    val bluntDamage: Double,
    val confidence: String,
    val layers: List<LayerSummary>,
    val burst: List<BurstSummary>,
    val rawJson: String,
)

data class LayerSummary(
    val name: String,
    val penetrationPercent: Int,
    val durabilityAfter: Double,
)

data class BurstSummary(
    val shot: Int,
    val penetrationPercent: Int,
    val killPercent: Int,
)

class PythonSimulationEngine {
    suspend fun calculate(scenarioJson: String): SimulationSummary =
        call("calculate_analytic_json", scenarioJson)

    suspend fun simulate(scenarioJson: String): SimulationSummary =
        call("simulate_json", scenarioJson)

    private suspend fun call(function: String, scenarioJson: String): SimulationSummary =
        withContext(Dispatchers.Default) {
        val api = Python.getInstance().getModule("tarkov_sim_core.api")
        val raw = api.callAttr(function, scenarioJson).toString()
        val root = JSONObject(raw)
        require(root.getBoolean("ok")) {
            root.optJSONArray("errors")?.toString() ?: "Simulation failed"
        }
        val result = root.getJSONObject("result")
        val layerArray = result.getJSONArray("layer_results")
        val layers = buildList {
            for (index in 0 until layerArray.length()) {
                val layer = layerArray.getJSONObject(index)
                add(
                    LayerSummary(
                        name = layer.getString("name"),
                        penetrationPercent =
                            (layer.getDouble("conditional_penetration_probability") * 100).toInt(),
                        durabilityAfter = layer.getDouble("expected_durability_after"),
                    ),
                )
            }
        }
        val penetration = result.getJSONArray("penetration_probability_by_shot")
        val kills = result.getJSONArray("kill_probability_by_shot")
        val burst = buildList {
            for (index in 0 until penetration.length()) {
                val kill = if (index < kills.length()) kills.getDouble(index) else 0.0
                add(
                    BurstSummary(
                        shot = index + 1,
                        penetrationPercent = (penetration.getDouble(index) * 100).toInt(),
                        killPercent = (kill * 100).toInt(),
                    ),
                )
            }
        }
        SimulationSummary(
            penetration = result.getDouble("final_penetration_probability"),
            threeShot = result.getDouble("three_shot_penetration_probability"),
            healthDamage = result.getDouble("expected_health_damage"),
            bluntDamage = result.getDouble("expected_blunt_damage"),
            confidence = result.getString("confidence"),
            layers = layers,
            burst = burst,
            rawJson = raw,
        )
    }

    suspend fun metadata(): String = withContext(Dispatchers.Default) {
        Python.getInstance()
            .getModule("tarkov_sim_core.api")
            .callAttr("get_engine_metadata_json")
            .toString()
    }
}
