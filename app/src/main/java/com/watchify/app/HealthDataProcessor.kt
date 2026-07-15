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

    fun init(context: Context) {
        if (dbHelper == null) {
            dbHelper = HealthDatabaseHelper(context.applicationContext)
            
            // Start the background consumer
            CoroutineScope(Dispatchers.IO).launch {
                for (record in channel) {
                    processRecord(record)
                }
            }
        }
    }

    // Producer API for BleManager to push raw packets immediately
    fun pushRecord(record: HealthRecord) {
        channel.trySend(record)
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
}
