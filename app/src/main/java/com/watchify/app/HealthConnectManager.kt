package com.watchify.app

import android.content.Context
import android.content.SharedPreferences
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.ZoneId
import java.time.temporal.ChronoUnit

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
        HealthPermission.getWritePermission(ExerciseSessionRecord::class),
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(OxygenSaturationRecord::class),
        HealthPermission.getReadPermission(BloodPressureRecord::class),
        HealthPermission.getReadPermission(BodyTemperatureRecord::class),
        HealthPermission.getReadPermission(BloodGlucoseRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class)
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

    suspend fun importLast30Days(): List<HealthRecord> {
        if (client == null || !hasAllPermissions()) return emptyList()
        val endTime = Instant.now()
        val startTime = endTime.minus(30, ChronoUnit.DAYS)
        val timeRange = TimeRangeFilter.between(startTime, endTime)
        
        val results = mutableListOf<HealthRecord>()
        try {
            client!!.readRecords(ReadRecordsRequest(StepsRecord::class, timeRange)).records.forEach {
                results.add(HealthRecord(HealthType.STEPS, it.startTime.epochSecond, it.count.toFloat()))
            }
            client!!.readRecords(ReadRecordsRequest(HeartRateRecord::class, timeRange)).records.forEach { hr ->
                hr.samples.forEach {
                    results.add(HealthRecord(HealthType.HEART_RATE, it.time.epochSecond, it.beatsPerMinute.toFloat()))
                }
            }
            client!!.readRecords(ReadRecordsRequest(OxygenSaturationRecord::class, timeRange)).records.forEach {
                results.add(HealthRecord(HealthType.SPO2, it.time.epochSecond, it.percentage.value.toFloat()))
            }
            client!!.readRecords(ReadRecordsRequest(BloodPressureRecord::class, timeRange)).records.forEach {
                results.add(HealthRecord(HealthType.BP, it.time.epochSecond, it.systolic.inMillimetersOfMercury.toFloat(), it.diastolic.inMillimetersOfMercury.toFloat()))
            }
            client!!.readRecords(ReadRecordsRequest(BodyTemperatureRecord::class, timeRange)).records.forEach {
                results.add(HealthRecord(HealthType.TEMP, it.time.epochSecond, it.temperature.inCelsius.toFloat()))
            }
            client!!.readRecords(ReadRecordsRequest(BloodGlucoseRecord::class, timeRange)).records.forEach {
                results.add(HealthRecord(HealthType.BG, it.time.epochSecond, it.level.inMillimolesPerLiter.toFloat()))
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return results
    }
}
