package com.eftcalculator.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import kotlinx.coroutines.flow.Flow
import java.io.File
import java.util.UUID

@Entity(tableName = "ammo")
data class AmmoEntity(
    @PrimaryKey val id: String,
    val name: String,
    val shortName: String,
    val caliber: String,
    val damage: Double,
    val penetrationPower: Double,
    val armorDamagePercent: Double,
    val projectileCount: Int,
    val initialSpeed: Double?,
    val source: String,
    val searchText: String,
    val nameZh: String? = null,
)

@Entity(tableName = "favorites")
data class FavoriteEntity(@PrimaryKey val ammoId: String)

@Dao
interface AmmoDao {
    @Query(
        """
        SELECT ammo.* FROM ammo
        LEFT JOIN favorites ON favorites.ammoId = ammo.id
        WHERE replace(lower(searchText), ' ', '') LIKE '%' || replace(lower(:query), ' ', '') || '%'
        ORDER BY favorites.ammoId IS NULL, caliber, shortName
        """,
    )
    fun search(query: String): Flow<List<AmmoEntity>>

    @Query(
        """
        SELECT ammo.* FROM ammo
        INNER JOIN favorites ON favorites.ammoId = ammo.id
        ORDER BY caliber, shortName
        """,
    )
    fun favorites(): Flow<List<AmmoEntity>>

    @Query("SELECT * FROM ammo ORDER BY caliber, shortName")
    suspend fun all(): List<AmmoEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<AmmoEntity>)

    @Query("DELETE FROM ammo WHERE id = :id")
    suspend fun deleteAmmo(id: String)

    @Query("DELETE FROM ammo")
    suspend fun clearAmmo()

    @Query("SELECT EXISTS(SELECT 1 FROM favorites WHERE ammoId = :id)")
    suspend fun isFavorite(id: String): Boolean

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun addFavorite(item: FavoriteEntity)

    @Query("DELETE FROM favorites WHERE ammoId = :id")
    suspend fun removeFavorite(id: String)
}

@Database(entities = [AmmoEntity::class, FavoriteEntity::class], version = 2, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun ammoDao(): AmmoDao

    companion object {
        @Volatile private var instance: AppDatabase? = null
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE ammo ADD COLUMN nameZh TEXT")
            }
        }

        fun build(context: Context, name: String): AppDatabase = Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                name,
            ).openHelperFactory(PreservingOpenHelperFactory()).addMigrations(MIGRATION_1_2).build()

        fun get(context: Context): AppDatabase = instance ?: synchronized(this) {
            instance ?: build(context, "eft-calculator.sqlite3").also { instance = it }
        }
    }
}

/** Save every original byte before Android's default corruption handler can delete it. */
class PreservingOpenHelperFactory : SupportSQLiteOpenHelper.Factory {
    override fun create(configuration: SupportSQLiteOpenHelper.Configuration): SupportSQLiteOpenHelper {
        val original = configuration.callback
        val callback = object : SupportSQLiteOpenHelper.Callback(original.version) {
            override fun onCreate(db: SupportSQLiteDatabase) = original.onCreate(db)
            override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = original.onUpgrade(db, oldVersion, newVersion)
            override fun onDowngrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = original.onDowngrade(db, oldVersion, newVersion)
            override fun onConfigure(db: SupportSQLiteDatabase) = original.onConfigure(db)
            override fun onOpen(db: SupportSQLiteDatabase) = original.onOpen(db)
            override fun onCorruption(db: SupportSQLiteDatabase) {
                val suffix = ".corrupt-${UUID.randomUUID()}.bak"
                for (ending in listOf("", "-wal", "-shm", "-journal")) {
                    val file = File(db.path + ending)
                    if (file.isFile) file.copyTo(File(file.path + suffix), overwrite = false)
                }
                original.onCorruption(db)
            }
        }
        val safe = SupportSQLiteOpenHelper.Configuration.builder(configuration.context)
            .name(configuration.name).callback(callback)
            .noBackupDirectory(configuration.useNoBackupDirectory).build()
        return FrameworkSQLiteOpenHelperFactory().create(safe)
    }
}
