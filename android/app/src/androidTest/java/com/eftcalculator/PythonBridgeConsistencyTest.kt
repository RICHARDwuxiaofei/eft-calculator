package com.eftcalculator

import androidx.test.core.app.ApplicationProvider
import com.eftcalculator.engine.PythonSimulationEngine
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PythonBridgeConsistencyTest {
    @Test
    fun allSharedVectorsMatchDesktopExpectations() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val names = context.assets.list("")!!.filter { it.endsWith(".tarkovsim.json") }
        assertEquals(6, names.size)
        names.forEach { name ->
            val vector = context.assets.open(name).bufferedReader().use { JSONObject(it.readText()) }
            val expected = vector.getJSONObject("expected")
            val result = PythonSimulationEngine().calculate(vector.getJSONObject("input").toString())
            assertEquals(name, expected.getDouble("final_penetration_probability"), result.penetration, 1e-12)
            assertEquals(name, expected.getDouble("expected_health_damage"), result.healthDamage, 1e-12)
            assertEquals(name, expected.getDouble("expected_blunt_damage"), result.bluntDamage, 1e-12)
        }
    }
}
