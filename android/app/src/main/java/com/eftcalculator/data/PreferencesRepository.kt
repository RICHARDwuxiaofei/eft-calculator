package com.eftcalculator.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("eft_settings")

class PreferencesRepository(private val context: Context) {
    private val laboratoryKey = booleanPreferencesKey("laboratory_mode")
    private val lastSyncKey = longPreferencesKey("last_sync_epoch_ms")
    private val sessionKey = stringPreferencesKey("last_session_json")

    val laboratoryMode = context.dataStore.data.map { it[laboratoryKey] ?: false }
    val lastSync = context.dataStore.data.map { it[lastSyncKey] ?: 0L }
    val session = context.dataStore.data.map { it[sessionKey] }

    suspend fun saveSession(json: String) {
        context.dataStore.edit { it[sessionKey] = json }
    }

    suspend fun setLaboratoryMode(enabled: Boolean) {
        context.dataStore.edit { it[laboratoryKey] = enabled }
    }

    suspend fun markSync(time: Long = System.currentTimeMillis()) {
        context.dataStore.edit { it[lastSyncKey] = time }
    }
}
