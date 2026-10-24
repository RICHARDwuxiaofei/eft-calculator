package com.eftcalculator

/** Same public API identifiers as the desktop normalization, including gauge aliases. */
fun displayCaliber(value: String): String {
    val cleaned = value.removePrefix("Caliber").replace("NATO", "").replace("mm", "").trim()
    val key = cleaned.lowercase().replace('×', 'x').filter { it.isLetterOrDigit() }
    return mapOf("9x18pm" to "9x18 PM", "9x19para" to "9x19", "9x33r" to ".357 Magnum",
        "1143x23acp" to ".45 ACP", "46x30" to "4.6x30", "57x28" to "5.7x28",
        "545x39" to "5.45x39", "58x42" to "5.8x42", "68x51" to "6.8x51", "556x45" to "5.56x45",
        "762x25tt" to "7.62x25 TT", "762x35" to ".300 BLK", "762x39" to "7.62x39", "762x51" to "7.62x51",
        "762x54r" to "7.62x54R", "127x55" to "12.7x55", "127x108" to "12.7x108",
        "366tkm" to ".366 TKM", "12g" to "12 gauge", "20g" to "20 gauge")[key] ?: cleaned
}

fun caliberMatches(value: String, selected: String): Boolean {
    if (selected.isBlank()) return true
    fun key(text: String) = displayCaliber(text).lowercase().filter { it.isLetterOrDigit() }
    val current = key(value)
    val target = key(selected)
    if (target in setOf("1270", "12gauge")) return current in setOf("1270", "1276", "12gauge")
    return current == target
}
