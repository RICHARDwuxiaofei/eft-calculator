package com.eftcalculator

import androidx.test.core.app.ApplicationProvider
import com.eftcalculator.engine.PythonSimulationEngine
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PythonBridgeConsistencyTest {
    @Test
    fun sharedSingleLayerVectorMatchesExpectedOutput() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val vector = context.assets.open("single_layer.tarkovsim.json")
            .bufferedReader()
            .use { JSONObject(it.readText()) }
        val expected = vector.getJSONObject("expected")
        val result = PythonSimulationEngine().calculate(vector.getJSONObject("input").toString())
        assertEquals(
            expected.getDouble("final_penetration_probability"),
            result.penetration,
            1e-12,
        )
        assertEquals(expected.getDouble("expected_health_damage"), result.healthDamage, 1e-12)
    }
}
