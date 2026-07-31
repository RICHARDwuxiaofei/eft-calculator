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
        val raw = fetchTarkovDev() ?: fetchTarkovTracker()
        val items = parseSnapshot(raw)
        require(items.size >= 20) { "Online snapshot count is suspicious: ${items.size}" }
        require(items.map { it.id }.toSet().size == items.size) { "Duplicate ammo IDs" }
        val database = AppDatabase.get(applicationContext)
        database.withTransaction {
            database.ammoDao().clearAmmo()
            database.ammoDao().upsertAll(items)
        }
        PreferencesRepository(applicationContext).markSync()
    }.fold(onSuccess = { Result.success() }, onFailure = { Result.retry() })

    private fun fetchTarkovDev(): String? {
        val query = """{"query":"query { ammo(lang: en) { item { id name shortName } caliber damage penetrationPower armorDamage projectileCount initialSpeed } }"}"""
        return request("https://api.tarkov.dev/graphql", "POST", query)
    }

    private fun fetchTarkovTracker(): String =
        requireNotNull(
            request(
                "https://raw.githubusercontent.com/TarkovTracker/tarkovdata/master/ammunition.json",
                "GET",
                null,
            ),
        )

    private fun request(url: String, method: String, body: String?): String? {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 25_000
        connection.setRequestProperty("Accept", "application/json")
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.bufferedWriter().use { it.write(body) }
        }
        if (connection.responseCode !in 200..299) return null
        return connection.inputStream.bufferedReader().use { it.readText() }
    }

    private fun parseSnapshot(raw: String): List<AmmoEntity> {
        val root = JSONObject(raw)
        val graph = root.optJSONObject("data")?.optJSONArray("ammo")
        if (graph != null) {
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
                            projectileCount = record.optInt("projectileCount", 1),
                            speed = record.optDouble("initialSpeed").takeUnless { it.isNaN() },
                            source = "tarkov.dev",
                        ),
                    )
                }
            }
        }
        return root.keys().asSequence().map { id ->
            val record = root.getJSONObject(id)
            val ballistics = record.getJSONObject("ballistics")
            entity(
                id = id,
                name = record.getString("name"),
                shortName = record.optString("shortName", record.getString("name")),
                caliber = record.getString("caliber").removePrefix("Caliber"),
                damage = ballistics.getDouble("damage"),
                penetration = ballistics.getDouble("penetrationPower"),
                armorDamage = ballistics.getDouble("armorDamage"),
                projectileCount = record.optInt("projectileCount", 1),
                speed = ballistics.optDouble("initialSpeed").takeUnless { it.isNaN() },
                source = "TarkovTracker/tarkovdata",
            )
        }.toList()
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
    ) = AmmoEntity(
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
        "$name $shortName $caliber",
    )

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
