package com.watchify.app

import android.content.Context
import android.content.SharedPreferences
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import java.time.Instant
import java.time.ZoneId

class HealthConnectManager(private val context: Context) {
    val client: HealthConnectClient? by lazy {
        if (HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE) {
            HealthConnectClient.getOrCreate(context)
        } else {
            null
        }
    }

    private val prefs: SharedPreferences = context.getSharedPreferences("HealthConnectPrefs", Context.MODE_PRIVATE)

    var isEnabled: Boolean
        get() = prefs.getBoolean("hc_enabled", false)
        set(value) = prefs.edit().putBoolean("hc_enabled", value).apply()

    val permissions = setOf(
        HealthPermission.getWritePermission(StepsRecord::class),
        HealthPermission.getWritePermission(HeartRateRecord::class),
        HealthPermission.getWritePermission(SleepSessionRecord::class),
        HealthPermission.getWritePermission(OxygenSaturationRecord::class),
        HealthPermission.getWritePermission(BloodPressureRecord::class),
        HealthPermission.getWritePermission(BodyTemperatureRecord::class),
        HealthPermission.getWritePermission(BloodGlucoseRecord::class),
        HealthPermission.getWritePermission(ExerciseSessionRecord::class)
    )

    suspend fun hasAllPermissions(): Boolean {
        if (client == null) return false
        val granted = client!!.permissionController.getGrantedPermissions()
        return granted.containsAll(permissions)
    }

    fun mapToHealthConnectRecord(record: HealthRecord): Record? {
        val time = Instant.ofEpochSecond(record.timestamp)
        val zoneOffset = ZoneId.systemDefault().rules.getOffset(time)
        return try {
            when (record.type) {
                HealthType.STEPS -> StepsRecord(
                    count = record.value1.toLong(),
                    startTime = time,
                    endTime = time.plusSeconds(60),
                    startZoneOffset = zoneOffset,
                    endZoneOffset = zoneOffset
                )
                HealthType.HEART_RATE -> HeartRateRecord(
                    startTime = time,
                    endTime = time.plusSeconds(60),
                    startZoneOffset = zoneOffset,
                    endZoneOffset = zoneOffset,
                    samples = listOf(HeartRateRecord.Sample(time, record.value1.toLong()))
                )
                HealthType.SPO2 -> OxygenSaturationRecord(
                    time = time,
                    zoneOffset = zoneOffset,
                    percentage = androidx.health.connect.client.units.Percentage(record.value1.toDouble())
                )
                HealthType.BP -> BloodPressureRecord(
                    time = time,
                    zoneOffset = zoneOffset,
                    systolic = androidx.health.connect.client.units.Pressure.millimetersOfMercury(record.value1.toDouble()),
                    diastolic = androidx.health.connect.client.units.Pressure.millimetersOfMercury(record.value2.toDouble())
                )
                HealthType.TEMP -> BodyTemperatureRecord(
                    time = time,
                    zoneOffset = zoneOffset,
                    temperature = androidx.health.connect.client.units.Temperature.celsius(record.value1.toDouble())
                )
                HealthType.BG -> BloodGlucoseRecord(
                    time = time,
                    zoneOffset = zoneOffset,
                    level = androidx.health.connect.client.units.BloodGlucose.millimolesPerLiter(record.value1.toDouble())
                )
                else -> null
            }
        } catch (e: Exception) {
            null
        }
    }

    suspend fun writeBatch(records: List<HealthRecord>) {
        if (client == null || records.isEmpty() || !isEnabled) return
        try {
            val mapped = records.mapNotNull { mapToHealthConnectRecord(it) }
            mapped.chunked(500).forEach { chunk ->
                client!!.insertRecords(chunk)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    suspend fun syncRecord(record: HealthRecord) {
        if (!isEnabled || client == null) return
        try {
            val mapped = mapToHealthConnectRecord(record)
            if (mapped != null) {
                client!!.insertRecords(listOf(mapped))
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
