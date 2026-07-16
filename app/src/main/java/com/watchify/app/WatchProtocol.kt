package com.watchify.app

import java.nio.ByteBuffer
import java.nio.ByteOrder

object WatchProtocol {
    private var pidCounter = 0

    /**
     * Builds the composite DEV_SYNC_SETTINGS (opcode 0x6E / 110) packet.
     * NOTE: SMS switch (0x7B) is intentionally excluded — it must be sent as a
     * standalone packet via buildSmsSwitchPayload() to avoid sub-packet framing corruption.
     */
    fun buildSyncSettingsPacket(
        isPairing: Boolean,
        callsEnabled: Boolean,
        appsEnabled: Boolean
    ): List<ByteArray> {
        val userInfo = byteArrayOf(0x0C, 0x00, 0x66.toByte(), 0xE8.toByte(), 0x03, 0x00, 0x00, 0x01, 0x19, 0xAF.toByte(), 0x46, 0x00)
        val language = byteArrayOf(0x04, 0x00, 0x67.toByte(), 0x00)

        // Time sub-packet
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

        val sensor    = byteArrayOf(0x04, 0x00, 0x6D.toByte(), 0x01)
        val callSwitch = byteArrayOf(0x04, 0x00, 0x7A.toByte(), if (callsEnabled) 1 else 0)

        val appBitmask = if (appsEnabled)
            byteArrayOf(0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte())
        else
            byteArrayOf(0x00, 0x00, 0x00, 0x00)
        val appSwitch  = byteArrayOf(0x08, 0x00, 0x7C.toByte(), 0x01, appBitmask[0], appBitmask[1], appBitmask[2], appBitmask[3])

        val pairFinish = byteArrayOf(0x05, 0x00, 0x78.toByte(), if (isPairing) 1 else 0, 0x00)

        // Ordered list of sub-packets — count is derived dynamically
        val subPacketList = listOf(userInfo, language, timeSubPacket, sensor, callSwitch, appSwitch, pairFinish)
        val subPackets = subPacketList.reduce { acc, b -> acc + b }
        val subPacketCount = subPacketList.size

        val totalLength = subPackets.size + 1
        val header = byteArrayOf(
            (totalLength and 0xFF).toByte(),
            ((totalLength shr 8) and 0xFF).toByte(),
            subPacketCount.toByte()
        )

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

    /**
     * Replace emoji and other non-watch-renderable code points with ASCII equivalents.
     * The watch display supports only GBK (ASCII + Chinese); multi-byte emoji crash or
     * display as garbage. Common emojis get a semantic text substitute; everything else
     * in the Supplementary Multilingual Plane is stripped.
     */
    private fun String.stripForWatch(): String {
        val sb = StringBuilder()
        this.codePoints().forEach { cp ->
            val replacement = when (cp) {
                // Faces
                0x1F600, 0x1F601, 0x1F603, 0x1F604, 0x1F606, 0x1F609, 0x1F60A, 0x1F642 -> ":)"
                0x1F610, 0x1F611, 0x1F614, 0x1F615, 0x1F641, 0x1F62C -> ":|"
                0x1F620, 0x1F621, 0x1F624, 0x1F625, 0x1F62D -> ":("
                0x1F602, 0x1F923 -> ":D"
                0x1F60D, 0x2764, 0x2665 -> "<3"
                0x1F494 -> "</3"
                0x1F44D -> "(+1)"
                0x1F44E -> "(-1)"
                0x1F44F -> "(clap)"
                0x1F525 -> "(fire)"
                0x2705 -> "(ok)"
                0x274C -> "(x)"
                0x26A0 -> "(!)"
                0x1F514, 0x1F515 -> "(bell)"
                0x1F4F1 -> "(phone)"
                0x1F4E7 -> "(email)"
                0x1F4AC -> "(msg)"
                0x1F4F8 -> "(camera)"
                0x23F0 -> "(alarm)"
                0x1F389, 0x1F38A -> "(party)"
                0x1F4AA -> "(strong)"
                0x1F4B0 -> "(money)"
                0x1F3E0 -> "(home)"
                0x2B50, 0x1F31F -> "*"
                // Strip anything in supplementary planes (emoji, pictographs, etc.)
                else -> if (cp > 0xFFFF) "" else null
            }
            if (replacement != null) {
                sb.append(replacement)
            } else {
                sb.appendCodePoint(cp)
            }
        }
        return sb.toString().trim()
    }

    fun buildNoticePayload(appId: Int, title: String, body: String): ByteArray {
        val cleanTitle = title.stripForWatch().take(24)
        val cleanBody  = body.stripForWatch().take(120)

        // OEM uses GBK for the title field (DataConvertUtils.f). UTF-8 is a safe cross-platform
        // fallback that correctly handles all scripts; pure-ASCII content is identical in both.
        val titleCharset = try { java.nio.charset.Charset.forName("GBK") } catch (e: Exception) { Charsets.UTF_8 }
        val titleBytes = cleanTitle.toByteArray(titleCharset)
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

    // -------------------------------------------------------------------------
    // BLE feature negotiation packets (sent during handshake)
    // -------------------------------------------------------------------------

    /**
     * DATA_TYPE_SUP_BLE_50 (opcode 29 / 0x1D).
     * Informs the watch whether the phone supports BLE 5.0 so it can select
     * the optimal PHY and connection interval. API 26+ devices are BLE 5 capable.
     */
    fun buildBle50SupportPacket(supported: Boolean): List<ByteArray> =
        buildMasterPacket(0, 1, 29, byteArrayOf(if (supported) 1 else 0))

    /**
     * DATA_TYPE_EXT_PID (opcode 31 / 0x1F).
     * Platform identifier — tells the watch which companion app family is connecting.
     * Universal = 8, ZK platform = 9. Defaults to Universal.
     */
    fun buildExtPidPacket(pid: Int = 8): List<ByteArray> =
        buildMasterPacket(0, 1, 31, byteArrayOf((pid and 0xFF).toByte()))

    fun buildFindDevicePacket(start: Boolean): List<ByteArray> {
        val payload = byteArrayOf(if (start) 1 else 0)
        return buildMasterPacket(0, 1, 11, payload) // 11 = DATA_TYPE_FIND_PHONE_OR_DEVICE
    }

    /**
     * Opcode 0x80 — DATA_TYPE_HEART_AUTO_SWITCH.
     * Enables/disables 24-hour continuous heart rate monitoring on the watch.
     *
     * Payload format (from OEM AutomaticHeartModel.java):
     *   byte[0] = state (1=on, 0=off)
     *   byte[1] = state (duplicated — firmware requires both bytes identical)
     *   byte[2..7] = 0x00 padding
     *
     * Must be sent on every connection — the watch does not persist this setting.
     */
    fun buildHeartAutoSwitchPacket(enabled: Boolean): List<ByteArray> {
        val state = if (enabled) 0x01.toByte() else 0x00.toByte()
        val payload = ByteArray(8)
        payload[0] = state
        payload[1] = state  // OEM duplicates the value in byte[1]
        return buildMasterPacket(0, 1, 0x80, payload)
    }

    /**
     * Opcode 0x88 — DATA_TYPE_TEMP_SETTING.
     * Enables automatic body temperature monitoring at a given interval.
     *
     * Payload format (from OEM TemperatureSettingModel.java):
     *   byte[0]   = tempSwitch (1=on, 0=off)
     *   byte[1-2] = interval in minutes as 2-byte little-endian (OEM default = 10)
     *
     * Must be sent on every connection.
     */
    fun buildTempMonitoringPacket(enabled: Boolean, intervalMinutes: Int = 10): List<ByteArray> {
        val sw = if (enabled) 0x01.toByte() else 0x00.toByte()
        val iLo = (intervalMinutes and 0xFF).toByte()
        val iHi = ((intervalMinutes shr 8) and 0xFF).toByte()
        return buildMasterPacket(0, 1, 0x88, byteArrayOf(sw, iLo, iHi))
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

