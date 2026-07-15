package com.watchify.app

import java.nio.ByteBuffer
import java.nio.ByteOrder

object WatchProtocol {
    private var pidCounter = 0
    private var seqCounter = 0

    // Handshake Payload translation
    val FULL_BIND_PAYLOAD = ("00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff" +
            "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000" +
            "00000000000000000000").chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    fun buildSyncSettingsPacket(
        isPairing: Boolean,
        callsEnabled: Boolean,
        smsEnabled: Boolean,
        appsEnabled: Boolean
    ): List<ByteArray> {
        val userInfo = byteArrayOf(0x0C, 0x00, 0x66.toByte(), 0xE8.toByte(), 0x03, 0x00, 0x00, 0x01, 0x19, 0xAF.toByte(), 0x46, 0x00)
        val language = byteArrayOf(0x04, 0x00, 0x67.toByte(), 0x00)
        
        // Time
        val timestamp = (System.currentTimeMillis() / 1000).toInt()
        val offset = (java.util.TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 1000).toInt()
        val timePayload = ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(timestamp)
            .putInt(offset)
            .put(0x00.toByte())
            .array()
        val timeSubPacket = ByteArray(12)
        timeSubPacket[0] = 12
        timeSubPacket[1] = 0
        timeSubPacket[2] = 0x68.toByte()
        System.arraycopy(timePayload, 0, timeSubPacket, 3, 9)
        
        val sensor = byteArrayOf(0x04, 0x00, 0x6D.toByte(), 0x01)
        val callSwitch = byteArrayOf(0x04, 0x00, 0x7A.toByte(), if (callsEnabled) 1 else 0)
        val smsSwitch = byteArrayOf(0x04, 0x00, 0x7B.toByte(), if (smsEnabled) 1 else 0)
        
        val appBitmask = if (appsEnabled) byteArrayOf(0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte()) else byteArrayOf(0x00, 0x00, 0x00, 0x00)
        val appSwitch = byteArrayOf(0x08, 0x00, 0x7C.toByte(), 0x01, appBitmask[0], appBitmask[1], appBitmask[2], appBitmask[3])
        
        val pairFinish = byteArrayOf(0x05, 0x00, 0x78.toByte(), if (isPairing) 1 else 0, 0x00)
        
        val subPackets = userInfo + language + timeSubPacket + sensor + callSwitch + smsSwitch + appSwitch + pairFinish
        
        val totalLength = subPackets.size + 1
        val header = ByteArray(3)
        header[0] = (totalLength and 0xFF).toByte()
        header[1] = ((totalLength shr 8) and 0xFF).toByte()
        header[2] = 8 // 8 subpackets
        
        val payload = header + subPackets
        return buildMasterPacket(0, 1, 110, payload)
    }

    @Synchronized
    fun buildMasterPacket(i: Int, i2: Int, opcode: Int, payload: ByteArray): List<ByteArray> {
        val length = payload.size
        if (length <= 10) {
            val pkt = ByteArray(20)
            pkt[0] = 0x00
            pkt[1] = (pidCounter and 0xFF).toByte()
            pkt[2] = 0x00
            pkt[3] = (i and 0xFF).toByte()
            pkt[4] = (i2 and 0xFF).toByte()
            pkt[5] = (opcode and 0xFF).toByte()
            pkt[8] = (length and 0xFF).toByte()
            pkt[9] = ((length shr 8) and 0xFF).toByte()
            System.arraycopy(payload, 0, pkt, 10, length)
            pidCounter = (pidCounter + 1) % 256
            return listOf(pkt)
        } else {
            val remaining = length - 10
            val addFrags = remaining / 19 + if (remaining % 19 > 0) 1 else 0
            val totalSize = (addFrags * 20) + 20
            val buffer = ByteArray(totalSize)

            buffer[0] = 0x00
            buffer[1] = (pidCounter and 0xFF).toByte()
            buffer[2] = (addFrags and 0xFF).toByte()
            buffer[3] = (i and 0xFF).toByte()
            buffer[4] = (i2 and 0xFF).toByte()
            buffer[5] = (opcode and 0xFF).toByte()
            buffer[8] = (length and 0xFF).toByte()
            buffer[9] = ((length shr 8) and 0xFF).toByte()
            System.arraycopy(payload, 0, buffer, 10, 10)

            for (f in 0 until addFrags) {
                val offset = (f + 1) * 20
                buffer[offset] = (f + 1).toByte()
                val start = 10 + (f * 19)
                val end = Math.min(start + 19, length)
                System.arraycopy(payload, start, buffer, offset + 1, end - start)
            }
            pidCounter = (pidCounter + 1) % 256

            val chunks = mutableListOf<ByteArray>()
            for (idx in 0 until totalSize step 20) {
                chunks.add(buffer.copyOfRange(idx, idx + 20))
            }
            return chunks
        }
    }

    fun getTimeSyncPayload(): ByteArray {
        val unixSec = (System.currentTimeMillis() / 1000).toInt()
        val offset = (java.util.TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 1000).toInt()
        val buffer = ByteBuffer.allocate(9).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putInt(unixSec)
        buffer.putInt(offset)
        buffer.put(0x01.toByte())
        return buffer.array()
    }

    fun buildNoticePayload(appId: Int, title: String, body: String): ByteArray {
        val cleanTitle = title.take(24)
        val cleanBody = body.take(120)
        
        // Title uses direct character-to-byte casting (like DataConvertUtils.f)
        val titleBytes = ByteArray(cleanTitle.length) { cleanTitle[it].code.toByte() }
        // Body uses standard UTF-8
        val bodyBytes = cleanBody.toByteArray(Charsets.UTF_8)
        
        val titleFieldType = 0x01.toByte() // 1 = Title/Sender field
        
        val items = ByteArray(1 + 1 + titleBytes.size + 1 + 1 + bodyBytes.size)
        var idx = 0
        items[idx++] = titleFieldType
        items[idx++] = titleBytes.size.toByte()
        System.arraycopy(titleBytes, 0, items, idx, titleBytes.size)
        idx += titleBytes.size
        items[idx++] = 0x02.toByte() // 2 = Body field
        items[idx++] = bodyBytes.size.toByte()
        System.arraycopy(bodyBytes, 0, items, idx, bodyBytes.size)
 
        val header = ByteBuffer.allocate(6).order(ByteOrder.LITTLE_ENDIAN)
        header.putInt((System.currentTimeMillis() / 1000).toInt())
        header.put(appId.toByte())
        header.put(2.toByte()) // 2 fields: Title/Sender and Body
 
        return header.array() + items
    }

    data class WeatherForecast(val weatherType: Int, val lowTemp: Int, val highTemp: Int)

    fun buildWeatherPacket(currentTemp: Int, forecastList: List<WeatherForecast>): List<ByteArray> {
        val bArr = if (forecastList.size > 3) ByteArray(19) else ByteArray((forecastList.size * 5) + 4)
        
        // Header must be the current unix timestamp in seconds (4 bytes, little-endian)
        val unixSec = (System.currentTimeMillis() / 1000).toInt()
        bArr[0] = (unixSec and 0xFF).toByte()
        bArr[1] = ((unixSec shr 8) and 0xFF).toByte()
        bArr[2] = ((unixSec shr 16) and 0xFF).toByte()
        bArr[3] = ((unixSec shr 24) and 0xFF).toByte()
        
        for (i in 0 until forecastList.size.coerceAtMost(3)) {
            val weather = forecastList[i]
            val idx = i * 5
            bArr[idx + 4] = weather.weatherType.toByte()
            bArr[idx + 5] = weather.lowTemp.toByte()
            bArr[idx + 6] = weather.highTemp.toByte()
            bArr[idx + 7] = 0.toByte()
            bArr[idx + 8] = 0.toByte()
        }
        
        return buildMasterPacket(0, 1, 105, bArr)
    }

    fun buildMenstrualPeriodPacket(
        startTimestampSec: Int,
        cycleLength: Int,
        menstrualLength: Int,
        reminderDayBefore: Int,
        reminderTimeHour: Int,
        reminderTimeMinute: Int,
        ovulationRemind: Int,
        ovulationDayRemind: Int,
        ovulationPeakRemind: Int,
        ovulationEndRemind: Int
    ): List<ByteArray> {
        val bArr = ByteArray(22)
        bArr[0] = 1.toByte() // enabled/activated type
        
        // Start Timestamp (4 bytes little-endian)
        bArr[1] = (startTimestampSec and 0xFF).toByte()
        bArr[2] = ((startTimestampSec shr 8) and 0xFF).toByte()
        bArr[3] = ((startTimestampSec shr 16) and 0xFF).toByte()
        bArr[4] = ((startTimestampSec shr 24) and 0xFF).toByte()
        
        bArr[5] = cycleLength.toByte()
        bArr[6] = menstrualLength.toByte()
        bArr[7] = reminderTimeHour.toByte()
        bArr[8] = reminderTimeMinute.toByte()
        bArr[9] = reminderDayBefore.toByte()
        bArr[10] = ovulationRemind.toByte()
        bArr[11] = ovulationDayRemind.toByte()
        bArr[12] = ovulationPeakRemind.toByte()
        bArr[13] = ovulationEndRemind.toByte()
        
        // remaining bytes [14..21] are 0 padding
        return buildMasterPacket(0, 1, 133, bArr)
    }



    private fun splitCoord(value: Double): ByteArray {
        val sign = if (value >= 0) 43.toByte() else 45.toByte() // ASCII '+' or '-'
        val absVal = Math.abs(value)
        var deg = absVal.toInt()
        var rem = (absVal - deg) * 60.0
        val minutes = rem.toInt()
        rem = (rem - minutes) * 60.0
        var seconds = rem.toInt()
        var frac = Math.round((rem - seconds) * 100.0).toInt()
        if (frac >= 100) {
            seconds += 1
            frac -= 100
        }
        return byteArrayOf(
            sign,
            deg.toByte(),
            minutes.toByte(),
            seconds.toByte(),
            (frac and 0xFF).toByte(),
            ((frac shr 8) and 0xFF).toByte()
        )
    }

    fun buildGpsPayload(lat: Double, lon: Double): ByteArray {
        val lonBytes = splitCoord(lon)
        val latBytes = splitCoord(lat)
        return lonBytes + latBytes
    }

    fun buildCardPayload(cardType: Int, url: String): ByteArray {
        val urlBytes = url.toByteArray(Charsets.UTF_8)
        val buffer = ByteBuffer.allocate(1 + 4 + urlBytes.size).order(ByteOrder.LITTLE_ENDIAN)
        buffer.put(cardType.toByte())
        buffer.putInt(urlBytes.size)
        buffer.put(urlBytes)
        return buffer.array()
    }

    fun buildMusicTitlePayload(song: String): ByteArray {
        val songArr = ByteArray(66)
        songArr[0] = 7 // Song Title content type
        val songBytes = song.toByteArray(Charsets.UTF_8).take(24).toByteArray()
        songArr[1] = songBytes.size.toByte()
        System.arraycopy(songBytes, 0, songArr, 2, songBytes.size)
        return songArr
    }

    fun buildMusicVolumePayload(volume: Int): ByteArray {
        val volArr = ByteArray(66)
        volArr[0] = 10 // Volume content type
        volArr[1] = 1 // Length
        volArr[2] = (volume and 0xFF).toByte()
        return volArr
    }

    fun buildCallsSwitchPayload(enabled: Boolean): ByteArray {
        return byteArrayOf(if (enabled) 1 else 0)
    }

    fun buildSmsSwitchPayload(enabled: Boolean): ByteArray {
        return byteArrayOf(if (enabled) 1 else 0)
    }

    fun buildAppSwitchPayload(masterEnabled: Boolean, bitmask: Int = 0x07FF): ByteArray {
        val buffer = ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
        buffer.put(if (masterEnabled) 1.toByte() else 0.toByte())
        buffer.putInt(bitmask)
        return buffer.array()
    }

    fun calculateCrc16(data: ByteArray): Int {
        var crc = 0
        for (b in data) {
            crc = crc.xor((b.toInt() and 0xFF) shl 8)
            for (i in 0 until 8) {
                if (crc and 0x8000 != 0) {
                    crc = (crc shl 1).xor(0x8005)
                } else {
                    crc = crc shl 1
                }
                crc = crc and 0xFFFF
            }
        }
        return crc
    }

    @Synchronized
    fun buildSecurePacket(opcode: Int, payload: ByteArray): ByteArray {
        val seq = (seqCounter % 256).toByte()
        val body = ByteArray(2 + payload.size)
        body[0] = seq
        body[1] = (opcode and 0xFF).toByte()
        System.arraycopy(payload, 0, body, 2, payload.size)

        val bodyWithCrcLen = body.size + 2
        val lengthPrefix = byteArrayOf(
            (bodyWithCrcLen and 0xFF).toByte(),
            ((bodyWithCrcLen shr 8) and 0xFF).toByte()
        )
        val crc = calculateCrc16(body)
        val crcBytes = byteArrayOf(
            (crc and 0xFF).toByte(),
            ((crc shr 8) and 0xFF).toByte()
        )

        seqCounter++
        return lengthPrefix + body + crcBytes
    }

    fun buildPaddedPacket(opcode: Int, payload: ByteArray): ByteArray {
        val totalLen = payload.size + 3
        val header = byteArrayOf(
            (totalLen and 0xFF).toByte(),
            ((totalLen shr 8) and 0xFF).toByte(),
            (opcode and 0xFF).toByte()
        )
        val rawPacket = header + payload
        val remainder = rawPacket.size % 20
        return if (remainder != 0) {
            val padLen = rawPacket.size + (20 - remainder)
            rawPacket.copyOf(padLen)
        } else {
            rawPacket
        }
    }

    fun buildFindDevicePacket(start: Boolean): List<ByteArray> {
        val payload = byteArrayOf(if (start) 1 else 0)
        return buildMasterPacket(0, 1, 11, payload) // 11 = DATA_TYPE_FIND_PHONE_OR_DEVICE
    }

    fun buildDataSyncRequests(): List<ByteArray> {
        val requests = mutableListOf<ByteArray>()
        // Opcode 3: Battery, Opcode 5: History Sport, Opcode 6: Sleep, Opcode 8: History Heart Rate
        requests.addAll(buildMasterPacket(0, 3, 3, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 5, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 6, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 8, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 18, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 20, ByteArray(0)))
        requests.addAll(buildMasterPacket(0, 3, 24, ByteArray(0))) // Body Temp
        requests.addAll(buildMasterPacket(0, 3, 27, ByteArray(0))) // Blood Glucose
        return requests
    }

    fun buildFastSyncRequests(): List<ByteArray> {
        return buildDataSyncRequests()
    }
}

