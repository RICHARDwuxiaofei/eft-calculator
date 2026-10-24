package com.eftcalculator

import androidx.test.core.app.ApplicationProvider
import com.eftcalculator.engine.PythonSimulationEngine
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import androidx.test.platform.app.InstrumentationRegistry

class PythonBridgeConsistencyTest {
    @Test
    fun independentDecimalCasesMatchEmbeddedCore() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().context
        val raw = context.assets.open("independent_cases_2026_10_25.json").bufferedReader().use { it.readText() }
        val rows = org.json.JSONArray(raw)
        assertEquals(92, rows.length())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val input = row.getJSONObject("input")
            val expected = row.getJSONObject("expected")
            val exact = input.getInt("shot_count") == 1 && input.getJSONObject("ammo").getInt("projectile_count") == 1
            val engine = PythonSimulationEngine()
            val result = if (exact) engine.calculate(input.toString()) else engine.simulate(input.toString())
            assertEquals(row.getString("id"), expected.getDouble("final_penetration_probability"), result.penetration, if (exact) 1e-10 else .008)
            assertEquals(row.getString("id"), expected.getDouble("expected_health_damage"), result.healthDamage, if (exact) 1e-10 else .8)
            assertEquals(row.getString("id"), expected.getDouble("expected_blunt_damage"), result.bluntDamage, if (exact) 1e-10 else .8)
        }
    }

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
