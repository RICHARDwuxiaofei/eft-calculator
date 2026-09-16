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
    val conditionalDamage: Double?,
    val burstDamage: Double,
    val intervalLow: Double,
    val intervalHigh: Double,
    val samples: Int,
    val method: String,
    val warnings: List<String>,
    val durability: List<List<Double>>,
    val dataVersion: String,
    val rulesetVersion: String,
)
data class LayerSummary(val name: String, val penetrationPercent: Double, val durabilityAfter: Double)
data class BurstSummary(val shot: Int, val penetrationPercent: Double, val killPercent: Double?)

class PythonSimulationEngine {
    suspend fun calculate(scenarioJson: String): SimulationSummary = call("calculate_analytic_json", scenarioJson)
    suspend fun simulate(scenarioJson: String): SimulationSummary = call("simulate_json", scenarioJson)

    private suspend fun call(function: String, scenarioJson: String): SimulationSummary = withContext(Dispatchers.Default) {
        val api = Python.getInstance().getModule("tarkov_sim_core.api")
        val raw = api.callAttr(function, scenarioJson).toString()
        val root = JSONObject(raw)
        require(root.getBoolean("ok")) { root.optJSONArray("errors")?.toString() ?: "Simulation failed" }
        val result = root.getJSONObject("result")
        val layerArray = result.getJSONArray("layer_results")
        val layers = (0 until layerArray.length()).map { i ->
            val layer = layerArray.getJSONObject(i)
            LayerSummary(layer.getString("name"), layer.getDouble("conditional_penetration_probability") * 100,
                layer.getDouble("expected_durability_after"))
        }
        val p = result.getJSONArray("penetration_probability_by_shot")
        val k = result.getJSONArray("kill_probability_by_shot")
        val burst = (0 until p.length()).map { i ->
            BurstSummary(i + 1, p.getDouble(i) * 100, if (i < k.length()) k.getDouble(i) * 100 else null)
        }
        val warnings = result.getJSONArray("warnings")
        val timeline = result.getJSONArray("durability_timeline")
        val durability = (0 until timeline.length()).map { i ->
            val row = timeline.getJSONObject(i).getJSONArray("durability")
            (0 until row.length()).map { row.getDouble(it) }
        }
        val interval = result.getJSONArray("penetration_confidence_interval")
        SimulationSummary(
            penetration = result.getDouble("final_penetration_probability"),
            threeShot = result.getDouble("three_shot_penetration_probability"),
            healthDamage = result.getDouble("expected_health_damage"),
            bluntDamage = result.getDouble("expected_blunt_damage"),
            confidence = result.getString("confidence"), layers = layers, burst = burst, rawJson = raw,
            conditionalDamage = result.optDouble("conditional_penetrating_damage").takeIf { it.isFinite() },
            burstDamage = result.getDouble("expected_burst_total_damage"),
            intervalLow = interval.getDouble(0), intervalHigh = interval.getDouble(1),
            samples = result.getInt("sample_count"), method = result.getString("method"),
            warnings = (0 until warnings.length()).map { warnings.getString(it) }, durability = durability,
            dataVersion = result.getString("data_version"), rulesetVersion = result.getString("ruleset_version"),
        )
    }

    suspend fun metadata(): String = withContext(Dispatchers.Default) {
        Python.getInstance().getModule("tarkov_sim_core.api").callAttr("get_engine_metadata_json").toString()
    }
}
