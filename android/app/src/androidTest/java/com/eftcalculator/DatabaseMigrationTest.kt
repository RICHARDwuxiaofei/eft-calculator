package com.eftcalculator

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.eftcalculator.data.AppDatabase
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DatabaseMigrationTest {
    @Test
    fun corruptDatabaseIsPreservedBeforeRecovery() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val name = "audit-corrupt-${System.nanoTime()}.sqlite3"
        val file = context.getDatabasePath(name)
        file.parentFile!!.mkdirs()
        val bytes = "corrupt-original-user-data-retained".toByteArray()
        file.writeBytes(bytes)
        val database = AppDatabase.build(context, name)
        try {
            // Some Android revisions recreate automatically, others report the error.
            runCatching { database.ammoDao().all() }
            val copies = file.parentFile!!.listFiles()!!.filter { it.name.startsWith(name + ".corrupt-") }
            assertTrue("Original database must survive the corruption handler", copies.any { it.readBytes().contentEquals(bytes) })
        } finally {
            database.close()
            context.deleteDatabase(name)
            file.parentFile!!.listFiles()!!.filter { it.name.startsWith(name + ".corrupt-") }.forEach { it.delete() }
        }
    }

    @Test
    fun versionOneDatabaseKeepsAmmoAndFavorite() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val name = "audit-migration-${System.nanoTime()}.sqlite3"
        context.openOrCreateDatabase(name, 0, null).use { db ->
            db.execSQL("CREATE TABLE ammo (id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, shortName TEXT NOT NULL, caliber TEXT NOT NULL, damage REAL NOT NULL, penetrationPower REAL NOT NULL, armorDamagePercent REAL NOT NULL, projectileCount INTEGER NOT NULL, initialSpeed REAL, source TEXT NOT NULL, searchText TEXT NOT NULL)")
            db.execSQL("CREATE TABLE favorites (ammoId TEXT NOT NULL PRIMARY KEY)")
            db.execSQL("INSERT INTO ammo VALUES ('test-id','Legacy ammo','L','5.56x45',49,44,47,1,945,'manual-override','legacy')")
            db.execSQL("INSERT INTO favorites VALUES ('test-id')")
            db.version = 1
        }
        val database = Room.databaseBuilder(context, AppDatabase::class.java, name)
            .addMigrations(AppDatabase.MIGRATION_1_2).build()
        try {
            val row = database.ammoDao().all().single()
            assertEquals("test-id", row.id)
            assertEquals(49.0, row.damage, 0.0)
            assertEquals("manual-override", row.source)
            assertTrue(database.ammoDao().isFavorite("test-id"))
            assertEquals(null, row.nameZh)
        } finally {
            database.close()
            context.deleteDatabase(name)
        }
    }
}
