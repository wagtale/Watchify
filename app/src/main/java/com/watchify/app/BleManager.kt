package com.watchify.app

import android.annotation.SuppressLint
import android.bluetooth.*
import android.content.Context
import android.content.Intent
import android.os.Build
import kotlinx.coroutines.*
import java.util.UUID
import android.media.AudioManager
import android.media.session.PlaybackState
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

@SuppressLint("MissingPermission")
class BleManager(private val context: Context) {

    private val logCallbacks = mutableListOf<(String) -> Unit>()
    private var lastConnectedMac: String? = null
    private var userDisconnectRequested = false
    private var autoReconnectJob: Job? = null

    fun registerLogCallback(cb: (String) -> Unit) {
        logCallbacks.add(cb)
    }

    fun unregisterLogCallback(cb: (String) -> Unit) {
        logCallbacks.remove(cb)
    }

    private fun logCallback(msg: String) {
        logCallbacks.forEach { it(msg) }
        android.util.Log.d("BleManager", msg)
    }

    private val bluetoothAdapter: BluetoothAdapter? = (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private var bluetoothGatt: BluetoothGatt? = null
    private var writeChar: BluetoothGattCharacteristic? = null

    private val WRITE_UUID = UUID.fromString("0000b002-0000-1000-8000-00805f9b34fb")
    private val NOTIFY_UUID = UUID.fromString("0000b001-0000-1000-8000-00805f9b34fb")
    private val SAME_SCREEN_NOTIFY_UUID = UUID.fromString("0000b008-0000-1000-8000-00805f9b34fb")
    private val SAME_SCREEN_WRITE_UUID = UUID.fromString("0000b009-0000-1000-8000-00805f9b34fb")

    var currentSong = "Starboy - The Weeknd"
    var currentVolume = 12
    var isListeningMusic = true



    private val MUSIC_ACTIONS = mapOf(
        1 to "PLAY", 2 to "PAUSE", 3 to "STOP", 4 to "PREVIOUS", 5 to "NEXT",
        6 to "PLAY_PAUSE_TOGGLE", 7 to "QUERY_MUSIC_INFO", 8 to "VOLUME_UP",
        9 to "VOLUME_DOWN", 10 to "QUERY_VOLUME_LEVEL"
    )

    fun pushMusicMetadata(song: String, vol: Int) {
        currentSong = song
        currentVolume = Math.max(0, Math.min(15, vol))
        CoroutineScope(Dispatchers.IO).launch {
            sendChunks(WatchProtocol.buildMasterPacket(0, 1, 113, WatchProtocol.buildMusicTitlePayload(currentSong)))
            sendChunks(WatchProtocol.buildMasterPacket(0, 1, 113, WatchProtocol.buildMusicVolumePayload(currentVolume)))
        }
    }

    fun startScan(callback: android.bluetooth.le.ScanCallback) {
        bluetoothAdapter?.bluetoothLeScanner?.startScan(callback)
    }

    fun stopScan(callback: android.bluetooth.le.ScanCallback) {
        bluetoothAdapter?.bluetoothLeScanner?.stopScan(callback)
    }

    fun attemptAutoConnect() {
        val prefs = context.getSharedPreferences("watch_prefs", Context.MODE_PRIVATE)
        val savedMac = prefs.getString("last_connected_mac", null)
        if (savedMac != null) {
            logCallback("[*] Found saved device: $savedMac. Auto-connecting...")
            lastConnectedMac = savedMac
            connect(savedMac)
        }
    }

    private fun scheduleAutoReconnect() {
        autoReconnectJob?.cancel()
        autoReconnectJob = CoroutineScope(Dispatchers.IO).launch {
            delay(5000)
            if (bluetoothGatt == null && lastConnectedMac != null) {
                logCallback("[*] Retrying watch connection ($lastConnectedMac)...")
                connect(lastConnectedMac!!)
            }
        }
    }

    fun connect(macAddress: String) {
        userDisconnectRequested = false
        val device = bluetoothAdapter?.getRemoteDevice(macAddress)
        if (device == null) {
            logCallback("[-] Device not found.")
            return
        }
        logCallback("[*] Connecting to $macAddress...")
        bluetoothGatt = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        
        // Save MAC address for auto-reconnection
        context.getSharedPreferences("watch_prefs", Context.MODE_PRIVATE)
            .edit()
            .putString("last_connected_mac", macAddress)
            .apply()
        lastConnectedMac = macAddress
    }

    fun disconnect() {
        userDisconnectRequested = true
        autoReconnectJob?.cancel()
        bluetoothGatt?.disconnect()
        bluetoothGatt?.close()
        bluetoothGatt = null
        writeChar = null
        logCallback("[*] Disconnected by user.")
    }

    fun isConnected(): Boolean = bluetoothGatt != null

    private val writeMutex = Mutex()

    suspend fun sendChunks(chunks: List<ByteArray>) {
        if (writeChar == null || bluetoothGatt == null) return
        writeMutex.withLock {
            withContext(Dispatchers.IO) {
                for (chunk in chunks) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        bluetoothGatt?.writeCharacteristic(writeChar!!, chunk, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
                    } else {
                        writeChar?.value = chunk
                        writeChar?.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                        bluetoothGatt?.writeCharacteristic(writeChar)
                    }
                    delay(30) // Wait 30ms to prevent buffer overflow, mimicking python asyncio.sleep(0.02)
                }
            }
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                logCallback("[+] Connected! Discovering services...")
                autoReconnectJob?.cancel()
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                logCallback("[-] Disconnected from watch.")
                writeChar = null
                bluetoothGatt = null
                if (!userDisconnectRequested && lastConnectedMac != null) {
                    logCallback("[*] Unexpected disconnect. Scheduling retry in 5s...")
                    scheduleAutoReconnect()
                }
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val service = gatt.services.find { it.characteristics.any { char -> char.uuid == WRITE_UUID } }
                if (service != null) {
                    writeChar = service.getCharacteristic(WRITE_UUID)
                    val notifyChar = service.getCharacteristic(NOTIFY_UUID)

                    CoroutineScope(Dispatchers.IO).launch {
                        // Enable notifications for primary notify char
                        gatt.setCharacteristicNotification(notifyChar, true)
                        val descriptor = notifyChar.getDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))
                        if (descriptor != null) {
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                            } else {
                                descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                                gatt.writeDescriptor(descriptor)
                            }
                            delay(300)
                        }

                        // Enable notifications for same screen notify char
                        val sameScreenNotifyChar = service.getCharacteristic(SAME_SCREEN_NOTIFY_UUID)
                        if (sameScreenNotifyChar != null) {
                            gatt.setCharacteristicNotification(sameScreenNotifyChar, true)
                            val sameScreenDesc = sameScreenNotifyChar.getDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))
                            if (sameScreenDesc != null) {
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                    gatt.writeDescriptor(sameScreenDesc, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                                } else {
                                    sameScreenDesc.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                                    gatt.writeDescriptor(sameScreenDesc)
                                }
                                delay(300)
                            }
                        }

                        logCallback("[>] Services discovered. Binding device...")
                        val syncPkt = WatchProtocol.buildSyncSettingsPacket(
                            isPairing = true,
                            callsEnabled = true,
                            smsEnabled = true,
                            appsEnabled = true
                        )
                        sendChunks(syncPkt)
                        logCallback("[+] Dynamic Settings Sync & Pair Finish Payload Sent!")
                        
                        // Auto-sync historical health data
                        logCallback("[>] Requesting historical health data...")
                        sendChunks(WatchProtocol.buildDataSyncRequests())
                    }
                }
            }
        }

        @Deprecated("Deprecated in Java")
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (characteristic.uuid == SAME_SCREEN_NOTIFY_UUID) {
                handleSameScreenData(characteristic.value)
            } else {
                handleIncomingData(characteristic.value)
            }
        }

        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            if (characteristic.uuid == SAME_SCREEN_NOTIFY_UUID) {
                handleSameScreenData(value)
            } else {
                handleIncomingData(value)
            }
        }

        @Deprecated("Deprecated in Java")
        override fun onCharacteristicRead(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val stringVal = String(characteristic.value, Charsets.UTF_8).replace(Regex("[^\\x20-\\x7E]"), "")
                logCallback("[🔍] Standard BLE Read (${characteristic.uuid.toString().substring(4, 8)}): $stringVal")
            }
        }

        override fun onCharacteristicRead(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val stringVal = String(value, Charsets.UTF_8).replace(Regex("[^\\x20-\\x7E]"), "")
                logCallback("[🔍] Standard BLE Read (${characteristic.uuid.toString().substring(4, 8)}): $stringVal")
            }
        }



        private fun parseUint32LE(data: ByteArray, offset: Int): Long {
            if (offset + 4 > data.size) return 0L
            return (data[offset].toLong() and 0xFF) or
                   ((data[offset + 1].toLong() and 0xFF) shl 8) or
                   ((data[offset + 2].toLong() and 0xFF) shl 16) or
                   ((data[offset + 3].toLong() and 0xFF) shl 24)
        }

        private var rxBuffer = ByteArray(0)
        private var expectedPayloadLen = 0
        private var currentPayloadLen = 0
        private var expectedFrags = 0
        private var currentFrag = -1
        private var currentHeader = ByteArray(10)

        private fun handleIncomingData(data: ByteArray) {
            try {
                if (data.isEmpty()) return

                if (data[0].toInt() == 0 && data.size >= 10) {
                    expectedFrags = data[2].toInt() and 0xFF
                    expectedPayloadLen = (data[8].toInt() and 0xFF) or ((data[9].toInt() and 0xFF) shl 8)
                    currentFrag = 0
                    currentHeader = data.copyOfRange(0, 10)
                    
                    val chunkLen = Math.min(data.size - 10, expectedPayloadLen)
                    rxBuffer = data.copyOfRange(10, 10 + chunkLen)
                    currentPayloadLen = chunkLen
                } 
                else if (data[0].toInt() > 0 && currentFrag >= 0 && data[0].toInt() == (currentFrag + 1) % 256) {
                    currentFrag = data[0].toInt() and 0xFF
                    val chunkLen = Math.min(data.size - 1, expectedPayloadLen - currentPayloadLen)
                    if (chunkLen > 0) {
                        rxBuffer += data.copyOfRange(1, 1 + chunkLen)
                        currentPayloadLen += chunkLen
                    }
                } 
                else {
                    return
                }

                if (currentFrag == expectedFrags) {
                    val header = currentHeader
                    val payload = rxBuffer
                    
                    rxBuffer = ByteArray(0)
                    expectedPayloadLen = 0
                    expectedFrags = 0
                    currentFrag = -1

                    processMasterPacket(header, payload)
                }
            } catch (e: Exception) {
                logCallback("[-] Error parsing packet: ${e.message}")
            }
        }

        private fun processMasterPacket(header: ByteArray, payload: ByteArray) {
            try {
                val seqCounter = header[3].toInt() and 0xFF
                val direction = header[4].toInt() and 0xFF
                val opcode = header[5].toInt() and 0xFF

            // Acknowledge incoming requests
            if (direction == 1 && opcode != 12) {
                CoroutineScope(Dispatchers.IO).launch {
                    sendChunks(WatchProtocol.buildMasterPacket(seqCounter, 4, opcode, byteArrayOf(1)))
                }
            }

            // 2. ACK responses
            if (direction == 4 && payload.size <= 1) {
                logCallback("[+] Received ACK for opcode $opcode")
                return
            }

            // Device Info (Opcode 2)
                if (opcode == 2) {
                    if (payload.isNotEmpty()) {
                        val hexDump = payload.joinToString(" ") { String.format("%02X", it) }
                        val decDump = payload.joinToString(".") { (it.toInt() and 0xFF).toString() }
                        logCallback("[🔍] MCU / Firmware Data (Decoded): v$decDump")
                        logCallback("[🔍] Raw Hex: $hexDump")
                    }
                    return
                }

                // Battery Info
                if (opcode == 3) {
                    if (payload.isNotEmpty()) {
                        val batteryLevel = payload[0].toInt() and 0xFF
                        logCallback("[🔋] Watch Battery: $batteryLevel%")
                        val intent = Intent("com.watchify.app.BATTERY_LEVEL")
                        intent.setPackage(context.packageName)
                        intent.putExtra("level", batteryLevel)
                        context.sendBroadcast(intent)
                    }
                    return
                }

                // Find Phone Watch Command
                if (opcode == 11) {
                    val isStart = payload.isNotEmpty() && payload[0].toInt() == 1
                    if (isStart) {
                        logCallback("[🚨] Watch is ringing your phone!")
                        context.sendBroadcast(Intent("com.watchify.app.FIND_PHONE_START").setPackage(context.packageName))
                    } else {
                        logCallback("[🚨] Watch stopped ringing your phone.")
                        context.sendBroadcast(Intent("com.watchify.app.FIND_PHONE_STOP").setPackage(context.packageName))
                    }
                    return
                }

                // 1. Time Sync requests
                if (opcode == 12) {
                    logCallback("[!] Watch requesting Time Sync...")
                    CoroutineScope(Dispatchers.IO).launch {
                        val ack = WatchProtocol.buildMasterPacket(seqCounter, 4, 12, byteArrayOf(1))
                        val sync = WatchProtocol.buildMasterPacket(0, 1, 104, WatchProtocol.getTimeSyncPayload())
                        sendChunks(ack)
                        sendChunks(sync)
                        logCallback("[+] Time Synced Auto-Acked.")
                    }
                    return
                }



                // 3. Music Control Buttons
                if (opcode == 14 && isListeningMusic && payload.isNotEmpty()) {
                    val actionId = payload[0].toInt() and 0xFF
                    val actionName = MUSIC_ACTIONS[actionId] ?: "UNKNOWN ($actionId)"
                    logCallback("[🎵 WATCH PRESS] Media Command: $actionName")

                    val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

                    when (actionId) {
                        1 -> { // PLAY
                            NotificationMonitor.getActiveController()?.transportControls?.play()
                            logCallback("  └── Triggered System Play")
                        }
                        2 -> { // PAUSE
                            NotificationMonitor.getActiveController()?.transportControls?.pause()
                            logCallback("  └── Triggered System Pause")
                        }
                        3 -> { // STOP
                            NotificationMonitor.getActiveController()?.transportControls?.stop()
                            logCallback("  └── Triggered System Stop")
                        }
                        4 -> { // PREVIOUS
                            NotificationMonitor.getActiveController()?.transportControls?.skipToPrevious()
                            logCallback("  └── Triggered System Skip Previous")
                        }
                        5 -> { // NEXT
                            NotificationMonitor.getActiveController()?.transportControls?.skipToNext()
                            logCallback("  └── Triggered System Skip Next")
                        }
                        6 -> { // PLAY_PAUSE_TOGGLE
                            val controller = NotificationMonitor.getActiveController()
                            if (controller != null) {
                                val pbState = controller.playbackState?.state
                                if (pbState == PlaybackState.STATE_PLAYING) {
                                    controller.transportControls.pause()
                                    logCallback("  └── Triggered System Pause (Toggle)")
                                } else {
                                    controller.transportControls.play()
                                    logCallback("  └── Triggered System Play (Toggle)")
                                }
                            }
                        }
                        7 -> { // QUERY_MUSIC_INFO
                            val track = NotificationMonitor.getCurrentTrackInfo()
                            val vol = NotificationMonitor.getCurrentVolume(context)
                            pushMusicMetadata(track, vol)
                        }
                        8 -> { // VOLUME_UP
                            audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
                            val track = NotificationMonitor.getCurrentTrackInfo()
                            val vol = NotificationMonitor.getCurrentVolume(context)
                            pushMusicMetadata(track, vol)
                            logCallback("  └── Volume increased to $vol/15")
                        }
                        9 -> { // VOLUME_DOWN
                            audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
                            val track = NotificationMonitor.getCurrentTrackInfo()
                            val vol = NotificationMonitor.getCurrentVolume(context)
                            pushMusicMetadata(track, vol)
                            logCallback("  └── Volume decreased to $vol/15")
                        }
                        10 -> { // QUERY_VOLUME_LEVEL
                            val track = NotificationMonitor.getCurrentTrackInfo()
                            val vol = NotificationMonitor.getCurrentVolume(context)
                            pushMusicMetadata(track, vol)
                        }
                        else -> {
                            logCallback("  └── Action Triggered: $actionName")
                        }
                    }
                    return
                }

                // 4. Steps History (Opcodes 4, 5)
                if (opcode == 4 || opcode == 5) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received Steps History: $recordCount records")
                        for (r in 0 until recordCount) {
                            val offset = 3 + (r * 20)
                            if (offset + 20 <= payload.size) {
                                val startTime = parseUint32LE(payload, offset)
                                val steps = parseUint32LE(payload, offset + 4)
                                val dist = parseUint32LE(payload, offset + 8)
                                val cal = parseUint32LE(payload, offset + 12)
                                val dur = parseUint32LE(payload, offset + 16)
                                val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000))
                                logCallback("  └── Steps Record: Date=$dateStr, Steps=$steps, Dist=${dist}m, Cal=${cal / 10.0}kcal, Dur=${dur}s")
                                
                                HealthDataProcessor.pushRecord(
                                    HealthRecord(HealthType.STEPS, startTime, steps.toFloat(), 0f)
                                )
                            }
                        }
                    }
                    val intent = Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 5. Sleep (Opcode 6)
                if (opcode == 6) {
                    if (payload.size >= 3) {
                        val sleepTypes = mapOf(0 to "NONE", 1 to "START", 2 to "DEEP", 3 to "LIGHT", 4 to "WAKE_UP")
                        var offset = 3
                        logCallback("[*] Received Sleep History")
                        while (offset < payload.size) {
                            val subCount = payload[offset].toInt() and 0xFF
                            if (subCount == 0) {
                                offset += 1
                                continue
                            }
                            for (s in 0 until subCount) {
                                val subOffset = offset + (s * 5)
                                if (subOffset + 5 <= payload.size) {
                                    val sleepType = payload[subOffset + 1].toInt() and 0xFF
                                    val startTime = parseUint32LE(payload, subOffset + 2)
                                    val typeName = sleepTypes[sleepType] ?: "UNKNOWN ($sleepType)"
                                    val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000))
                                    logCallback("  └── Sleep Record: Date=$dateStr, Type=$typeName")
                                    
                                    HealthDataProcessor.pushRecord(
                                        HealthRecord(HealthType.SLEEP, startTime, sleepType.toFloat(), 0f)
                                    )
                                }
                            }
                            offset += (subCount * 5) + 1
                        }
                    }
                    val intent = Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 6. Heart Rate (Opcodes 7, 8, 17)
                if (opcode == 7 || opcode == 8 || opcode == 17) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        val logName = if (opcode == 17) "Exercise Heart Rate" else "Heart Rate"
                        logCallback("[*] Received $logName History: $recordCount records")
                        for (r in 0 until recordCount) {
                            val offset = 3 + (r * 5)
                            if (offset + 5 <= payload.size) {
                                val startTime = parseUint32LE(payload, offset)
                                val hr = payload[offset + 4].toInt() and 0xFF
                                val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000))
                                logCallback("  └── $logName Record: Date=$dateStr, HR=$hr bpm")
                                
                                HealthDataProcessor.pushRecord(
                                    HealthRecord(HealthType.HEART_RATE, startTime, hr.toFloat(), 0f)
                                )
                            }
                        }
                    }
                    val intent = Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 7. Audio BLE MAC Address (Opcode 23)
                if (opcode == 23) {
                    if (payload.size >= 6) {
                        val macParts = payload.copyOfRange(0, 6).map { String.format("%02X", it) }
                        val macAddress = macParts.joinToString(":")
                        logCallback("[🎵 AUDIO MAC] Received watch audio MAC: $macAddress")
                        
                        try {
                            val audioDevice = bluetoothAdapter?.getRemoteDevice(macAddress)
                            if (audioDevice != null) {
                                if (audioDevice.bondState != BluetoothDevice.BOND_BONDED) {
                                    logCallback("[*] Initiating classic Bluetooth pairing with $macAddress...")
                                    audioDevice.createBond()
                                } else {
                                    logCallback("[+] Watch classic Bluetooth already paired.")
                                }
                            }
                        } catch (e: Exception) {
                            logCallback("[-] Failed to initiate audio pairing: ${e.message}")
                        }
                    }
                    return
                }

                // 8. Silent OEM telemetry handling (prevents unhandled logs)
                if (opcode == 1 || opcode == 21 || opcode == 101 || opcode == 103 || opcode == 120 || opcode == 161) {
                    return
                }


                // 9. Blood Pressure (Opcode 18)
                if (opcode == 18) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received Blood Pressure History: $recordCount records")
                        for (r in 0 until recordCount) {
                            val offset = 3 + (r * 6)
                            if (offset + 6 <= payload.size) {
                                val startTime = parseUint32LE(payload, offset)
                                val systolic = payload[offset + 4].toInt() and 0xFF
                                val diastolic = payload[offset + 5].toInt() and 0xFF
                                val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000))
                                logCallback("  └── Blood Pressure Record: Date=$dateStr, Sys=$systolic, Dia=$diastolic")
                                
                                HealthDataProcessor.pushRecord(
                                    HealthRecord(HealthType.BP, startTime, systolic.toFloat(), diastolic.toFloat())
                                )
                            }
                        }
                    }
                    val intent = android.content.Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 10. Blood Oxygen (Opcode 20)
                if (opcode == 20) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received SpO2 History: $recordCount records")
                        for (r in 0 until recordCount) {
                            val offset = 3 + (r * 5)
                            if (offset + 5 <= payload.size) {
                                val startTime = parseUint32LE(payload, offset)
                                val spo2 = payload[offset + 4].toInt() and 0xFF
                                val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000))
                                logCallback("  └── SpO2 Record: Date=$dateStr, SpO2=$spo2%")
                                
                                HealthDataProcessor.pushRecord(
                                    HealthRecord(HealthType.SPO2, startTime, spo2.toFloat(), 0f)
                                )
                            }
                        }
                    }
                    val intent = android.content.Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 10.5 Body Temperature (Opcode 24)
                if (opcode == 24) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received Body Temp History: $recordCount records")
                        if (recordCount > 0) {
                            val recordSize = (payload.size - 3) / recordCount
                            for (r in 0 until recordCount) {
                                val offset = 3 + (r * recordSize)
                                if (offset + recordSize <= payload.size && recordSize >= 4) {
                                    val startTime = parseUint32LE(payload, offset)
                                    val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000L))
                                    var tempVal = 0f
                                    if (recordSize >= 6) { 
                                        val rawLow = payload[offset + 4].toInt() and 0xFF
                                        val rawHigh = payload[offset + 5].toInt() and 0xFF
                                        val rawInt = rawLow or (rawHigh shl 8)
                                        tempVal = rawInt / 100f // e.g. 3620 -> 36.2 C
                                    }
                                    logCallback("  └── Temp Record: Date=$dateStr, Val=$tempVal °C")
                                    
                                    HealthDataProcessor.pushRecord(
                                        HealthRecord(HealthType.TEMP, startTime, tempVal, 0f)
                                    )
                                }
                            }
                        }
                    }
                    val intent = android.content.Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 11. Blood Glucose (Opcode 27)
                if (opcode == 27) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received Blood Glucose History: $recordCount records")
                        if (recordCount > 0) {
                            val recordSize = (payload.size - 3) / recordCount
                            for (r in 0 until recordCount) {
                                val offset = 3 + (r * recordSize)
                                if (offset + recordSize <= payload.size && recordSize >= 4) {
                                    val startTime = parseUint32LE(payload, offset)
                                    val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000L))
                                    val dataBytes = payload.copyOfRange(offset + 4, offset + recordSize).map { String.format("%02X", it) }.joinToString(" ")
                                    var glucoseVal = 0f
                                    if (recordSize >= 6) { // 4 bytes time + 2 bytes data
                                        val rawLow = payload[offset + 4].toInt() and 0xFF
                                        val rawHigh = payload[offset + 5].toInt() and 0xFF
                                        val rawInt = rawLow or (rawHigh shl 8)
                                        glucoseVal = rawInt / 100f // e.g. 585 -> 5.85 mmol/L
                                    }
                                    logCallback("  └── Glucose Record: Date=$dateStr, RawBytes=[$dataBytes], Val=$glucoseVal mmol/L")
                                    
                                    HealthDataProcessor.pushRecord(
                                        HealthRecord(HealthType.BG, startTime, glucoseVal, 0f)
                                    )
                                }
                            }
                        }
                    }
                    val intent = Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                // 12. HRV (Opcode 35)
                if (opcode == 35) {
                    if (payload.size >= 3) {
                        val recordCount = payload[2].toInt() and 0xFF
                        logCallback("[*] Received HRV History: $recordCount records")
                        if (recordCount > 0) {
                            val recordSize = (payload.size - 3) / recordCount
                            for (r in 0 until recordCount) {
                                val offset = 3 + (r * recordSize)
                                if (offset + recordSize <= payload.size && recordSize >= 4) {
                                    val startTime = parseUint32LE(payload, offset)
                                    val dateStr = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US).format(java.util.Date(startTime * 1000L))
                                    var hrvVal = 0f
                                    if (recordSize >= 5) {
                                        hrvVal = (payload[offset + 4].toInt() and 0xFF).toFloat()
                                    }
                                    logCallback("  └── HRV Record: Date=$dateStr, Val=$hrvVal ms")
                                    
                                    HealthDataProcessor.pushRecord(
                                        HealthRecord(HealthType.HRV, startTime, hrvVal, 0f)
                                    )
                                }
                            }
                        }
                    }
                    val intent = Intent("com.watchify.app.HEALTH_DATA_UPDATED")
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    return
                }

                val hexDump = payload.joinToString("") { String.format("%02X ", it) }
                logCallback("[?] Received unhandled packet: Opcode $opcode | Payload: $hexDump")
            } catch (e: Throwable) {
                logCallback("[-] Process Error: ${e.message}")
            }
        }
    }

    suspend fun sendSameScreenWrite(payload: ByteArray) {
        val sameScreenWriteChar = writeChar?.service?.getCharacteristic(SAME_SCREEN_WRITE_UUID)
        if (sameScreenWriteChar != null && bluetoothGatt != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                bluetoothGatt?.writeCharacteristic(sameScreenWriteChar, payload, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
            } else {
                sameScreenWriteChar.value = payload
                sameScreenWriteChar.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                bluetoothGatt?.writeCharacteristic(sameScreenWriteChar)
            }
        }
    }

    private fun handleSameScreenData(value: ByteArray) {
        if (value.size > 2 && value[0] == 0xAA.toByte() && value[1] == 0x55.toByte()) {
            val op = value[2].toInt() and 0xFF
            logCallback("[📷 CAMERA] Recv SameScreen command: $op (payload size: ${value.size - 3})")
            
            if (op == 0) {
                logCallback("[📷 CAMERA] Close Camera screen")
                context.sendBroadcast(android.content.Intent(CameraActivity.ACTION_CLOSE_CAMERA))
            } else if (op == 1) {
                logCallback("[📷 CAMERA] Watch opened Camera screen. Launching preview activity...")
                try {
                    val intent = android.content.Intent(context, CameraActivity::class.java).apply {
                        addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    context.startActivity(intent)
                    
                    CoroutineScope(Dispatchers.IO).launch {
                        delay(200)
                        sendSameScreenWrite(byteArrayOf(0xAA.toByte(), 0x55.toByte(), 0x04.toByte(), 0x01.toByte()))
                    }
                } catch (e: Exception) {
                    logCallback("[-] Failed to launch Camera: ${e.message}")
                }
            } else if (op == 2) {
                logCallback("[📷 CAMERA] Shutter Clicked! Triggering photo capture...")
                context.sendBroadcast(android.content.Intent(CameraActivity.ACTION_TAKE_PHOTO))
            }
        }
    }
    fun readStandardDeviceStrings() {
        val deviceService = bluetoothGatt?.getService(UUID.fromString("0000180a-0000-1000-8000-00805f9b34fb"))
        if (deviceService != null) {
            CoroutineScope(Dispatchers.IO).launch {
                val chars = listOf(
                    "00002a24-0000-1000-8000-00805f9b34fb", // Model
                    "00002a25-0000-1000-8000-00805f9b34fb", // Serial
                    "00002a26-0000-1000-8000-00805f9b34fb", // Firmware
                    "00002a27-0000-1000-8000-00805f9b34fb", // Hardware
                    "00002a28-0000-1000-8000-00805f9b34fb", // Software
                    "00002a29-0000-1000-8000-00805f9b34fb"  // Manufacturer
                )
                logCallback("[*] Querying standard BLE chipset records...")
                for (uuid in chars) {
                    val char = deviceService.getCharacteristic(UUID.fromString(uuid))
                    if (char != null) {
                        try {
                            bluetoothGatt?.readCharacteristic(char)
                        } catch (e: SecurityException) {
                            e.printStackTrace()
                        }
                        delay(500)
                    }
                }
            }
        } else {
            logCallback("[-] Standard Device Information Service (180A) is not exposed by this chipset.")
        }
    }
}
