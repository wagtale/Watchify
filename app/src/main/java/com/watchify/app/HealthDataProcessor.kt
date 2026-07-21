package com.watchify.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileWriter

enum class HealthType {
    HEART_RATE, STEPS, SLEEP, SPO2, BP, BG, TEMP, HRV, SPORT
}

data class HealthRecord(
    val type: HealthType,
    val timestamp: Long,
    val value1: Float,
    val value2: Float = 0f
)

class HealthDatabaseHelper(context: Context) : SQLiteOpenHelper(context, "health_index.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE records (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "type TEXT, " +
                    "timestamp INTEGER, " +
                    "value1 REAL, " +
                    "value2 REAL, " +
                    "UNIQUE(type, timestamp) ON CONFLICT REPLACE)"
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Preserve data across version upgrades by copying to a temporary table
        db.execSQL("ALTER TABLE records RENAME TO records_old")
        onCreate(db)
        
        // Attempt to copy over existing data, ignoring new columns (they will be null/default)
        try {
            db.execSQL("INSERT INTO records (type, timestamp, value1, value2) SELECT type, timestamp, value1, value2 FROM records_old")
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            db.execSQL("DROP TABLE IF EXISTS records_old")
        }
    }
}

object HealthDataProcessor {
    // Channel acts as our internal message queue/broker (like Kafka topic)
    private val channel = Channel<HealthRecord>(Channel.UNLIMITED)
    
    // Flow to emit update events to the UI
    private val _updates = MutableSharedFlow<HealthType>(extraBufferCapacity = 10)
    val updates = _updates.asSharedFlow()

    private var dbHelper: HealthDatabaseHelper? = null
    lateinit var hcManager: HealthConnectManager

    fun init(context: Context) {
        if (dbHelper == null) {
            hcManager = HealthConnectManager(context.applicationContext)
            dbHelper = HealthDatabaseHelper(context.applicationContext)
            
            // Start the background consumer
            CoroutineScope(Dispatchers.IO).launch {
                for (record in channel) {
                    processRecord(record)
                }
            }
        }
    }

    // Producer API for BleManager to push raw packets immediately.
    // Records that fail the sanity check are silently dropped — the watch sends
    // 0.0-padded placeholders when a sensor has no reading for a time slot.
    fun pushRecord(record: HealthRecord) {
        if (record.isValid()) channel.trySend(record)
    }

    /**
     * Returns true if the record contains a physiologically plausible, non-zero measurement.
     * Each type has its own range derived from real-world medical limits.
     */
    private fun HealthRecord.isValid(): Boolean {
        if (timestamp <= 0L) return false
        return when (type) {
            HealthType.HEART_RATE -> value1 >= 30f  && value1 <= 250f   // bpm
            HealthType.STEPS      -> value1 >  0f                        // at least 1 step
            HealthType.SLEEP      -> value1 >  0f                        // 0 = NONE / no data
            HealthType.SPO2       -> value1 >= 50f  && value1 <= 100f   // %
            HealthType.BP         -> value1 >= 40f  && value2 >= 20f    // systolic / diastolic mmHg
            HealthType.BG         -> value1 >  0f   && value1 <= 50f    // mmol/L (>50 = sensor error)
            HealthType.TEMP       -> value1 >= 30f  && value1 <= 45f    // °C (hypothermia–hyperthermia)
            HealthType.HRV        -> value1 >  0f
            HealthType.SPORT      -> value1 >  0f   && value2 >  0f    // sportId + duration both non-zero
        }
    }

    // Consumer Logic: Persist and index the record
    private suspend fun processRecord(record: HealthRecord) {
        val db = dbHelper?.writableDatabase ?: return
        val values = ContentValues().apply {
            put("type", record.type.name)
            put("timestamp", record.timestamp)
            put("value1", record.value1)
            put("value2", record.value2)
        }
        db.insert("records", null, values)
        
        if (hcManager.isEnabled) {
            hcManager.syncRecord(record)
        }
        
        // Notify subscribers (MainActivity UI)
        _updates.emit(record.type)
    }

    // Consumer API for UI to pull indexed data
    fun getHistory(type: HealthType, limit: Int = 20): List<HealthRecord> {
        val db = dbHelper?.readableDatabase ?: return emptyList()
        val cursor = db.rawQuery(
            "SELECT timestamp, value1, value2 FROM records WHERE type = ? ORDER BY timestamp ASC",
            arrayOf(type.name)
        )
        val result = mutableListOf<HealthRecord>()
        while (cursor.moveToNext()) {
            result.add(
                HealthRecord(
                    type,
                    cursor.getLong(0),
                    cursor.getFloat(1),
                    cursor.getFloat(2)
                )
            )
        }
        cursor.close()
        return result.takeLast(limit)
    }

    fun exportToCsv(context: Context): File? {
        val db = dbHelper?.readableDatabase ?: return null
        val exportFile = File(context.getExternalFilesDir(null), "watchify_health_export.csv")
        try {
            val writer = FileWriter(exportFile)
            writer.append("Type,Timestamp,Value1,Value2\n")
            val cursor = db.rawQuery("SELECT type, timestamp, value1, value2 FROM records ORDER BY timestamp ASC", null)
            if (cursor.moveToFirst()) {
                do {
                    val type = cursor.getString(0)
                    val ts = cursor.getLong(1)
                    val v1 = cursor.getFloat(2)
                    val v2 = cursor.getFloat(3)
                    writer.append("$type,$ts,$v1,$v2\n")
                } while (cursor.moveToNext())
            }
            cursor.close()
            writer.flush()
            writer.close()
            return exportFile
        } catch (e: Exception) {
            e.printStackTrace()
            return null
        }
    }

    suspend fun backfillToHealthConnect() {
        val db = dbHelper?.readableDatabase ?: return
        val cursor = db.rawQuery("SELECT type, timestamp, value1, value2 FROM records ORDER BY timestamp ASC", null)
        val allRecords = mutableListOf<HealthRecord>()
        if (cursor.moveToFirst()) {
            do {
                try {
                    allRecords.add(HealthRecord(
                        HealthType.valueOf(cursor.getString(0)),
                        cursor.getLong(1),
                        cursor.getFloat(2),
                        cursor.getFloat(3)
                    ))
                } catch (e: Exception) {}
            } while (cursor.moveToNext())
        }
        cursor.close()
        hcManager.writeBatch(allRecords)
    }

    suspend fun importFromHealthConnect() {
        val imported = hcManager.importLast30Days()
        val db = dbHelper?.writableDatabase ?: return
        
        imported.forEach { record ->
            val values = ContentValues().apply {
                put("type", record.type.name)
                put("timestamp", record.timestamp)
                put("value1", record.value1)
                put("value2", record.value2)
            }
            db.insert("records", null, values)
        }
    }
}
