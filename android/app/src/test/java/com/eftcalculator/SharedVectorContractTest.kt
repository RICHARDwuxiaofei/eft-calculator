package com.eftcalculator

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SharedVectorContractTest {
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
}
