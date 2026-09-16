package com.eftcalculator.data

import android.content.Context
import androidx.room.withTransaction
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit
import org.json.JSONObject

class DataSyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = runCatching {
        val raw = requireNotNull(fetchTarkovDev()) { "Current data unavailable; keeping the verified offline catalog" }
        val items = parseSnapshot(raw)
        require(items.size >= 20) { "Online snapshot count is suspicious: ${items.size}" }
        require(items.map { it.id }.toSet().size == items.size) { "Duplicate ammo IDs" }
        val database = AppDatabase.get(applicationContext)
        database.withTransaction {
            database.ammoDao().upsertAll(items)
        }
        PreferencesRepository(applicationContext).markSync()
    }.fold(onSuccess = { Result.success() }, onFailure = { Result.retry() })

    private fun fetchTarkovDev(): String? {
        val query = """
            query EftCalculatorAmmoBilingual {
              en: ammo(lang: en) {
                item { id name shortName }
                caliber damage penetrationPower armorDamage projectileCount initialSpeed
              }
              zh: ammo(lang: zh) { item { id name shortName } }
            }
        """.trimIndent()
        return request(
            "https://api.tarkov.dev/graphql",
            "POST",
            JSONObject().put("query", query).toString(),
        )
    }

    private fun request(url: String, method: String, body: String?): String? {
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 25_000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("User-Agent", "EFT-Calculator-Android/2.2")
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.bufferedWriter().use { it.write(body) }
        }
        if (connection.responseCode !in 200..299) return null
        return connection.inputStream.bufferedReader().use { it.readText() }
        } finally { connection.disconnect() }
    }

    private fun parseSnapshot(raw: String): List<AmmoEntity> {
        val root = JSONObject(raw)
        require(!root.has("errors")) { "Upstream query returned errors" }
        val data = root.optJSONObject("data")
        val graph = data?.optJSONArray("en") ?: data?.optJSONArray("ammo")
        if (graph != null) {
            val chineseNames = buildMap {
                val chinese = data?.optJSONArray("zh")
                if (chinese != null) {
                    for (index in 0 until chinese.length()) {
                        val item = chinese.getJSONObject(index).getJSONObject("item")
                        put(item.getString("id"), item.optString("name").takeIf { it.isNotBlank() })
                    }
                }
            }
            return buildList {
                for (index in 0 until graph.length()) {
                    val record = graph.getJSONObject(index)
                    val item = record.getJSONObject("item")
                    add(
                        entity(
                            id = item.getString("id"),
                            name = item.getString("name"),
                            shortName = item.optString("shortName", item.getString("name")),
                            caliber = record.getString("caliber").removePrefix("Caliber"),
                            damage = record.getDouble("damage"),
                            penetration = record.getDouble("penetrationPower"),
                            armorDamage = record.getDouble("armorDamage"),
                            projectileCount = record.getInt("projectileCount").also {
                                require(record.getDouble("projectileCount") == it.toDouble())
                            },
                            speed = record.optDouble("initialSpeed").takeUnless { it.isNaN() },
                            source = "tarkov.dev",
                            nameZh = chineseNames[item.getString("id")],
                        ),
                    )
                }
            }
        }
        error("Unsupported or historical-only snapshot; existing data retained")
    }

    private fun entity(
        id: String,
        name: String,
        shortName: String,
        caliber: String,
        damage: Double,
        penetration: Double,
        armorDamage: Double,
        projectileCount: Int,
        speed: Double?,
        source: String,
        nameZh: String? = null,
    ): AmmoEntity {
        require(damage.isFinite() && damage >= 0)
        require(penetration.isFinite() && penetration >= 0)
        require(armorDamage.isFinite() && armorDamage in 0.0..100.0)
        require(projectileCount in 1..64)
        require(speed == null || (speed.isFinite() && speed > 0))
        require(id.matches(Regex("[a-f0-9]{24}")))
        return AmmoEntity(
        id,
        name,
        shortName,
        caliber,
        damage,
        penetration,
        armorDamage,
        projectileCount,
        speed,
        source,
        "$name ${nameZh.orEmpty()} $shortName $caliber",
        nameZh,
    )
    }

    companion object {
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<DataSyncWorker>(6, TimeUnit.HOURS)
                .setConstraints(
                    androidx.work.Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                )
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "eft-data-sync",
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
