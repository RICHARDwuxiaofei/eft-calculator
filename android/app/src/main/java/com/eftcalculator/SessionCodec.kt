package com.eftcalculator

import com.eftcalculator.data.AmmoEntity
import org.json.JSONArray
import org.json.JSONObject

/** Saved inputs only; results are always recalculated with the installed shared core. */
object SessionCodec {
    fun encode(state: CalculatorState): String {
        val root = JSONObject().put("version", 1).put("distance", state.distance)
            .put("shots", state.shots).put("bodyPart", state.bodyPart).put("distanceDecay", state.distanceDecay)
        state.selectedAmmo?.let { a ->
            root.put("ammo", JSONObject().put("id", a.id).put("name", a.name).put("shortName", a.shortName)
                .put("caliber", a.caliber).put("damage", a.damage).put("penetration", a.penetrationPower)
                .put("armorDamage", a.armorDamagePercent).put("pellets", a.projectileCount)
                .put("speed", a.initialSpeed ?: JSONObject.NULL).put("source", a.source)
                .put("searchText", a.searchText).put("nameZh", a.nameZh ?: JSONObject.NULL))
        }
        root.put("armor", JSONArray().apply {
            state.armor.forEach { a -> put(JSONObject().put("name", a.name).put("class", a.armorClass)
                .put("material", a.material).put("durability", a.durability).put("original", a.maximum)
                .put("repaired", a.repairedMaximum).put("carrier", a.carrierId).put("slot", a.slot)
                .put("type", a.layerType).put("blunt", a.bluntThroughput).put("enabled", a.enabled).put("itemId", a.itemId)) }
        })
        return root.toString()
    }

    fun decode(raw: String): CalculatorState {
        val root = JSONObject(raw)
        require(root.getInt("version") == 1)
        val ammo = root.optJSONObject("ammo")?.let { a ->
            AmmoEntity(a.getString("id"), a.getString("name"), a.getString("shortName"), a.getString("caliber"),
                a.getDouble("damage"), a.getDouble("penetration"), a.getDouble("armorDamage"), a.getInt("pellets"),
                a.optDouble("speed").takeIf { it.isFinite() && it > 0 }, a.getString("source"),
                a.getString("searchText"), if (a.isNull("nameZh")) null else a.getString("nameZh"))
        }
        if (ammo != null) {
            require(ammo.damage.isFinite() && ammo.damage >= 0 && ammo.penetrationPower.isFinite() && ammo.penetrationPower >= 0)
            require(ammo.armorDamagePercent.isFinite() && ammo.armorDamagePercent in 0.0..100.0 && ammo.projectileCount in 1..64)
        }
        val armor = root.getJSONArray("armor")
        require(armor.length() <= 12)
        val layers = (0 until armor.length()).map { index ->
            val a = armor.getJSONObject(index)
            ArmorInput(a.getInt("class"), a.getString("material"), a.getDouble("durability").toFloat(),
                a.getDouble("original").toFloat(), a.getString("name"), a.getString("carrier"), a.getString("slot"),
                a.getDouble("repaired").toFloat(), a.getString("type"), a.getDouble("blunt"), a.getBoolean("enabled"), a.getString("itemId")).also {
                require(it.armorClass in 1..6 && it.layerType in listOf("plate", "soft", "helmet"))
                require(it.material in listOf("ceramic", "steel", "aramid", "uhmwpe", "titanium", "aluminum", "glass", "combined"))
                require(it.maximum.isFinite() && it.repairedMaximum.isFinite() && it.durability.isFinite())
                require(it.maximum > 0 && it.repairedMaximum > 0 && it.repairedMaximum <= it.maximum && it.durability in 0f..it.repairedMaximum)
                require(it.bluntThroughput.isFinite() && it.bluntThroughput in 0.0..1.0)
            }
        }
        val distance = root.getInt("distance")
        val shots = root.getInt("shots")
        val body = root.getString("bodyPart")
        require(distance in 0..1000 && shots in 1..20 && body in listOf("head", "thorax", "stomach"))
        return CalculatorState(ammo, layers, distance, shots, bodyPart = body, distanceDecay = root.getBoolean("distanceDecay"))
    }
}

fun matchesAmmoQuery(item: AmmoEntity, query: String): Boolean {
    fun normalize(value: String) = value.lowercase().replace('×', 'x').filter { it.isLetterOrDigit() }
    val text = normalize("${item.name} ${item.shortName} ${item.caliber} ${item.nameZh.orEmpty()} ${item.searchText}")
    return query.split(Regex("\\s+")).map(::normalize).filter { it.isNotEmpty() }.all { it in text }
}
