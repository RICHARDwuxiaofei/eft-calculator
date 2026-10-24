package com.eftcalculator

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SharedVectorContractTest {
    @Test
    fun apiCalibersAndGaugeAliasesUseTheSameFilters() {
        assertEquals("5.8x42", displayCaliber("Caliber58x42"))
        assertEquals("5.56x45", displayCaliber("Caliber556x45NATO"))
        assertTrue(caliberMatches("556x45", "5.56x45"))
        assertTrue(caliberMatches("12/76", "12/70"))
        assertTrue(!caliberMatches("5.45x39", "5.56x45"))
    }
    @Test
    fun sharedVectorsUseSchemaOneAndExpectedOutputs() {
        val directory = File("../../shared/test_vectors")
        val vectors = directory.listFiles { file -> file.name.endsWith(".tarkovsim.json") }
            ?.sortedBy { it.name }
            .orEmpty()
        assertEquals(6, vectors.size)
        vectors.forEach { file ->
            val root = JSONObject(file.readText())
            assertEquals(1, root.getJSONObject("input").getInt("schema_version"))
            assertTrue(root.getJSONObject("expected").has("final_penetration_probability"))
        }
    }

    @Test
    fun sessionPreservesInputsAndDoesNotPersistResults() {
        val original = CalculatorState(armor = listOf(ArmorInput(durability = 25f, repairedMaximum = 35f)),
            shots = 7, distance = 125, bodyPart = "stomach", distanceDecay = true)
        val restored = SessionCodec.decode(SessionCodec.encode(original))
        assertEquals(original, restored)
    }

    @Test(expected = IllegalArgumentException::class)
    fun repairedMaximumZeroIsRejectedBeforeSharedCore() {
        SessionCodec.decode(SessionCodec.encode(CalculatorState(armor = listOf(ArmorInput(repairedMaximum = 0f, durability = 0f)))))
    }
}
