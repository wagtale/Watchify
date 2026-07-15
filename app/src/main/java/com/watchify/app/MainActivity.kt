package com.watchify.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.res.ResourcesCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity() {

    private lateinit var bleManager: BleManager
    private lateinit var logView: TextView
    private lateinit var connectionBadge: TextView
    private lateinit var batteryBadge: TextView
    private lateinit var graphView: GraphView
    private lateinit var stepsGraph: GraphView
    private lateinit var sleepGraph: GraphView
    private lateinit var spo2Graph: GraphView
    private lateinit var bpGraph: GraphView
    private lateinit var bgGraph: GraphView
    private lateinit var tempGraph: GraphView
    private lateinit var cityInput: android.widget.EditText
    private val statusHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private var batteryPollTick = 0
    private val statusUpdater = object : Runnable {
        override fun run() {
            updateConnectionStatus()
            
            if (::bleManager.isInitialized && bleManager.isConnected()) {
                batteryPollTick++
                if (batteryPollTick >= 10) { // Every 10 seconds
                    batteryPollTick = 0
                    CoroutineScope(Dispatchers.IO).launch {
                        bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 3, 3, ByteArray(0)))
                    }
                }
            }
            
            statusHandler.postDelayed(this, 1000)
        }
    }
    private val statusReceiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                "com.watchify.app.BATTERY_LEVEL" -> {
                    val level = intent.getIntExtra("level", -1)
                    if (level in 0..100) {
                        runOnUiThread {
                            batteryBadge.text = "$level%"
                            val color = if (level > 20) "#34C759" else "#FF3B30"
                            batteryBadge.setTextColor(Color.parseColor(color))
                        }
                    }
                }
                "com.watchify.app.HEALTH_DATA_UPDATED" -> {
                    updateHealthGraph()
                }
                "com.watchify.app.CITY_UPDATED" -> {
                    val city = intent.getStringExtra("city")
                    if (!city.isNullOrEmpty()) {
                        runOnUiThread {
                            if (this@MainActivity::cityInput.isInitialized) {
                                cityInput.setText(city)
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateConnectionStatus()
        val filter = android.content.IntentFilter("com.watchify.app.BATTERY_LEVEL")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(statusReceiver, filter)
        }
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
    }

    private val logCallback: (String) -> Unit = { msg ->
        runOnUiThread {
            logView.append("\n$msg")
            val scroll = logView.parent as? ScrollView
            scroll?.post { scroll.fullScroll(View.FOCUS_DOWN) }
        }
    }
    
    // Discovery lists and scanner state
    private val discoveredDevices = mutableListOf<android.bluetooth.BluetoothDevice>()
    private val discoveredNames = mutableListOf<String>()
    private var deviceSpinner: Spinner? = null
    private var isScanning = false
    private var weatherJob: kotlinx.coroutines.Job? = null

    private val scanCallback = object : android.bluetooth.le.ScanCallback() {
        override fun onScanResult(callbackType: Int, result: android.bluetooth.le.ScanResult?) {
            val device = result?.device ?: return
            val name = result.scanRecord?.deviceName ?: device.name ?: "Unknown Device"
            val mac = device.address
            val displayName = "$name ($mac)"
            
            runOnUiThread {
                if (!discoveredDevices.any { it.address == mac }) {
                    discoveredDevices.add(device)
                    discoveredNames.add(displayName)
                    deviceSpinner?.let { spinner ->
                        val adapter = spinner.adapter as ArrayAdapter<String>
                        adapter.notifyDataSetChanged()
                    }
                }
            }
        }
    }

    private lateinit var hrValueText: TextView
    private lateinit var stepsValueText: TextView
    private lateinit var sleepValueText: TextView
    private lateinit var spo2ValueText: TextView
    private lateinit var bpValueText: TextView
    private lateinit var bgValueText: TextView
    private lateinit var tempValueText: TextView

    private var healthUpdateJob: kotlinx.coroutines.Job? = null
    private lateinit var analyticsContainer: LinearLayout

    private fun updateHealthGraph() {
        runOnUiThread {
            // Heart Rate
            val hrHistory = HealthDataProcessor.getHistory(HealthType.HEART_RATE, 20)
            if (hrHistory.isNotEmpty() && ::graphView.isInitialized) {
                val hrValues = hrHistory.map { it.value1 }
                graphView.setData(hrValues)
                hrValueText.text = "${hrValues.last().toInt()} bpm"
            }
            
            // Steps
            val stepsHistory = HealthDataProcessor.getHistory(HealthType.STEPS, 20)
            if (stepsHistory.isNotEmpty() && ::stepsGraph.isInitialized) {
                val stepsValues = stepsHistory.map { it.value1 }
                stepsGraph.setData(stepsValues)
                stepsValueText.text = "${stepsValues.last().toInt()} steps"
            }
            
            // Sleep
            val sleepHistory = HealthDataProcessor.getHistory(HealthType.SLEEP, 20)
            if (sleepHistory.isNotEmpty() && ::sleepGraph.isInitialized) {
                val sleepValues = sleepHistory.map { it.value1 }
                sleepGraph.setData(sleepValues)
                sleepValueText.text = "${sleepValues.last()} type"
            }
            
            // SpO2
            val spo2History = HealthDataProcessor.getHistory(HealthType.SPO2, 20)
            if (spo2History.isNotEmpty() && ::spo2Graph.isInitialized) {
                val spo2Values = spo2History.map { it.value1 }
                spo2Graph.setData(spo2Values)
                spo2ValueText.text = "${spo2Values.last().toInt()}%"
            }
            
            // Blood Pressure
            val bpHistory = HealthDataProcessor.getHistory(HealthType.BP, 20)
            if (bpHistory.isNotEmpty() && ::bpGraph.isInitialized) {
                val sysValues = bpHistory.map { it.value1 }
                val diaValues = bpHistory.map { it.value2 }
                bpGraph.setMultiData(listOf(sysValues, diaValues))
                bpValueText.text = "${sysValues.last().toInt()}/${diaValues.last().toInt()} mmHg"
            }
            
            // Blood Glucose
            val bgHistory = HealthDataProcessor.getHistory(HealthType.BG, 20)
            if (bgHistory.isNotEmpty() && ::bgGraph.isInitialized) {
                val bgValues = bgHistory.map { it.value1 }
                bgGraph.setData(bgValues)
                bgValueText.text = "${bgValues.last()} mmol/L"
            }
            
            // Body Temp
            val tempHistory = HealthDataProcessor.getHistory(HealthType.TEMP, 20)
            if (tempHistory.isNotEmpty() && ::tempGraph.isInitialized) {
                val tempValues = tempHistory.map { it.value1 }
                tempGraph.setData(tempValues)
                tempValueText.text = "${tempValues.last()} °C"
            }
        }
        updateAnalyticsView()
    }
    
    private fun updateAnalyticsView() {
        val hrValues = HealthDataProcessor.getHistory(HealthType.HEART_RATE, 20).map { it.value1 }
        val sysValues = HealthDataProcessor.getHistory(HealthType.BP, 20).map { it.value1 }
        val diaValues = HealthDataProcessor.getHistory(HealthType.BP, 20).map { it.value2 }
        val spo2Values = HealthDataProcessor.getHistory(HealthType.SPO2, 20).map { it.value1 }
        val bgValues = HealthDataProcessor.getHistory(HealthType.BG, 20).map { it.value1 }
        val sleepValues = HealthDataProcessor.getHistory(HealthType.SLEEP, 20).map { it.value1 }
        val tempValues = HealthDataProcessor.getHistory(HealthType.TEMP, 20).map { it.value1 }
        
        val analysis = HealthAnalyticsEngine.analyzeAll(hrValues, sysValues, diaValues, spo2Values, bgValues, sleepValues, tempValues)
        
        runOnUiThread {
            if (!::analyticsContainer.isInitialized) return@runOnUiThread
            
            if (analyticsContainer.childCount > 1) {
                analyticsContainer.removeViews(1, analyticsContainer.childCount - 1)
            }
            
            val scoreCard = createCard("GENERAL HEALTH SCORE", TextView(this@MainActivity).apply {
                text = "${analysis.first}/100"
                textSize = 48f
                setTextColor(if (analysis.first >= 80) Color.parseColor("#34C759") else if (analysis.first >= 60) Color.parseColor("#FFCC00") else Color.parseColor("#FF3B30"))
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                gravity = android.view.Gravity.CENTER
            })
            analyticsContainer.addView(scoreCard)
            
            for (metric in analysis.second) {
                val statusColor = when (metric.status) {
                    "Normal" -> "#34C759"
                    "Under" -> "#FFCC00"
                    else -> "#FF3B30"
                }
                val metricText = TextView(this@MainActivity).apply {
                    text = "${metric.metricName}: ${metric.status}\n${metric.message}"
                    textSize = 16f
                    setTextColor(Color.parseColor(statusColor))
                    typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                }
                analyticsContainer.addView(createCard("INSIGHT", metricText))
            }
            
            analyticsContainer.addView(createCard("COMBINED GRAPHS", 
                TextView(this@MainActivity).apply { text = "Heart Rate"; setTextColor(Color.WHITE) },
                GraphView(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300); setData(hrValues) },
                TextView(this@MainActivity).apply { text = "Blood Pressure"; setTextColor(Color.WHITE) },
                GraphView(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300); setMultiData(listOf(sysValues, diaValues)) },
                TextView(this@MainActivity).apply { text = "SpO2"; setTextColor(Color.WHITE) },
                GraphView(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300); setData(spo2Values) },
                TextView(this@MainActivity).apply { text = "Blood Glucose"; setTextColor(Color.WHITE) },
                GraphView(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300); setData(bgValues) },
                TextView(this@MainActivity).apply { text = "Body Temperature"; setTextColor(Color.WHITE) },
                GraphView(this@MainActivity).apply { layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300); setData(tempValues) }
            ))
        }
    }

    private fun startScanning() {
        if (isScanning) return
        discoveredDevices.clear()
        discoveredNames.clear()
        discoveredNames.add("Select discovered device...")
        deviceSpinner?.let { spinner ->
            val adapter = spinner.adapter as ArrayAdapter<String>
            adapter.notifyDataSetChanged()
        }
        
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }

        val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 2)
            return
        }
        
        try {
            isScanning = true
            logView.append("\n[*] Starting watch search (BLE scan)...")
            bleManager.startScan(scanCallback)
            
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                stopScanning()
            }, 10000)
        } catch (e: Exception) {
            logView.append("\n[-] Scan error: ${e.message}")
            isScanning = false
        }
    }

    private fun stopScanning() {
        if (!isScanning) return
        try {
            bleManager.stopScan(scanCallback)
            logView.append("\n[*] Scan stopped.")
        } catch (e: Exception) {
            logView.append("\n[-] Stop scan error: ${e.message}")
        }
        isScanning = false
    }

    // Default MAC address
    private val DEFAULT_MAC = "A1:B2:CC:09:78:0F"


    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        
        // Initialize the Kafka-like Health Processor
        HealthDataProcessor.init(this)
        
        // Initial render of stored data on startup
        updateHealthGraph()
        
        healthUpdateJob = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
            HealthDataProcessor.updates.collect {
                updateHealthGraph()
            }
        }
        
        bleManager = BleManager(this)

        val requiredPermissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.CAMERA
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            requiredPermissions.add(Manifest.permission.BLUETOOTH_SCAN)
            requiredPermissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        val missingPermissions = requiredPermissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missingPermissions.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missingPermissions.toTypedArray(), 100)
        } else {
            startDriverServiceIfPermitted()
        }

        bleManager = WatchApplication.instance.bleManager
        bleManager.registerLogCallback(logCallback)
        statusHandler.post(statusUpdater)

        val homeScroll = ScrollView(this).apply {
            isFillViewport = true
            clipToPadding = false
            setPadding(0, 320, 0, 320)
            isVerticalScrollBarEnabled = false
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 64, 32, 64)
        }
        homeScroll.addView(container)

        val healthScroll = ScrollView(this).apply {
            isFillViewport = true
            visibility = View.GONE
            clipToPadding = false
            setPadding(0, 320, 0, 320)
            isVerticalScrollBarEnabled = false
        }

        val healthContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 64, 32, 64)
            
            val healthTitle = TextView(this@MainActivity).apply {
                text = "Health & Activity"
                textSize = 34f
                setTextColor(Color.WHITE)
                typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                setPadding(16, 0, 16, 32)
            }
            addView(healthTitle)
            
            graphView = GraphView(this@MainActivity)
            stepsGraph = GraphView(this@MainActivity)
            sleepGraph = GraphView(this@MainActivity)
            spo2Graph = GraphView(this@MainActivity)
            bpGraph = GraphView(this@MainActivity)
            bgGraph = GraphView(this@MainActivity)
            tempGraph = GraphView(this@MainActivity)
            
            hrValueText = createValueTextView()
            stepsValueText = createValueTextView()
            sleepValueText = createValueTextView()
            spo2ValueText = createValueTextView()
            bpValueText = createValueTextView()
            bgValueText = createValueTextView()
            tempValueText = createValueTextView()
            
            addView(createExpandableHealthCard("Heart Rate", R.drawable.ic_heart, graphView, 8, hrValueText))
            addView(createExpandableHealthCard("Steps", R.drawable.ic_activity, stepsGraph, 5, stepsValueText))
            addView(createExpandableHealthCard("Sleep", R.drawable.ic_moon, sleepGraph, 6, sleepValueText))
            addView(createExpandableHealthCard("Blood Oxygen", R.drawable.ic_droplet, spo2Graph, 20, spo2ValueText))
            addView(createExpandableHealthCard("Blood Pressure", R.drawable.ic_stethoscope, bpGraph, 18, bpValueText))
            addView(createExpandableHealthCard("Blood Glucose", R.drawable.ic_activity, bgGraph, 27, bgValueText))
            addView(createExpandableHealthCard("Body Temperature", R.drawable.ic_activity, tempGraph, 24, tempValueText))
        }
        healthScroll.addView(healthContainer)

        val analyticsScroll = ScrollView(this).apply {
            isFillViewport = true
            visibility = View.GONE
            clipToPadding = false
            setPadding(0, 320, 0, 320)
            isVerticalScrollBarEnabled = false
        }
        
        analyticsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 64, 32, 64)
            val title = TextView(this@MainActivity).apply {
                text = "Analytics & Insights"
                textSize = 34f
                setTextColor(Color.WHITE)
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                setPadding(16, 0, 16, 32)
            }
            addView(title)
        }
        analyticsScroll.addView(analyticsContainer)

        val contentFrame = FrameLayout(this).apply {
            layoutParams = FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT)
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(
                    Color.parseColor("#0F2027"),
                    Color.parseColor("#203A43"),
                    Color.parseColor("#2C5364")
                )
            )
            addView(homeScroll)
            addView(healthScroll)
            addView(analyticsScroll)
        }

        val headerContent = LinearLayout(this).apply {
            id = View.generateViewId()
            layoutParams = android.widget.RelativeLayout.LayoutParams(android.widget.RelativeLayout.LayoutParams.MATCH_PARENT, android.widget.RelativeLayout.LayoutParams.WRAP_CONTENT)
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            setPadding(48, 32, 48, 32)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#40000000")) // Glass
                setStroke(2, Color.parseColor("#4DFFFFFF"))
                cornerRadius = 64f
            }
            
            val appTitle = TextView(this@MainActivity).apply {
                text = "Watchify"
                textSize = 28f
                setTextColor(Color.WHITE)
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            
            connectionBadge = TextView(this@MainActivity).apply {
                text = "Disconnected"
                textSize = 14f
                setTextColor(Color.parseColor("#FF3B30"))
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                setPadding(24, 12, 24, 12)
                background = GradientDrawable().apply {
                    setColor(Color.parseColor("#1C1C1E"))
                    cornerRadius = 16f
                }
            }
            
            batteryBadge = TextView(this@MainActivity).apply {
                text = "--%"
                textSize = 14f
                setTextColor(Color.WHITE)
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                setPadding(32, 16, 32, 16)
                layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                    setMargins(16, 0, 0, 0)
                }
                background = GradientDrawable().apply {
                    setColor(Color.parseColor("#40000000"))
                    cornerRadius = 32f
                }
                val battIcon = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_battery_full)
                battIcon?.setBounds(0, 0, 48, 48)
                setCompoundDrawables(battIcon, null, null, null)
                compoundDrawablePadding = 16
            }
            
            addView(appTitle)
            addView(connectionBadge)
            addView(batteryBadge)
        }
        val headerGlass = GlassView(this).apply {
            layoutParams = android.widget.RelativeLayout.LayoutParams(android.widget.RelativeLayout.LayoutParams.MATCH_PARENT, 0).apply {
                addRule(android.widget.RelativeLayout.ALIGN_TOP, headerContent.id)
                addRule(android.widget.RelativeLayout.ALIGN_BOTTOM, headerContent.id)
            }
        }
        val headerLayout = android.widget.RelativeLayout(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(32, 64, 32, 0)
                gravity = android.view.Gravity.TOP
            }
            elevation = 16f
            clipToOutline = true
            outlineProvider = object : android.view.ViewOutlineProvider() {
                override fun getOutline(view: View, outline: android.graphics.Outline) {
                    outline.setRoundRect(0, 0, view.width, view.height, 64f)
                }
            }
            addView(headerGlass)
            addView(headerContent)
        }

        // 1. Connection Card
        discoveredNames.add("Select discovered device...")
        val spinner = createSpinner(discoveredNames)
        deviceSpinner = spinner

        val scanBtn = createButton("Scan Devices", "#1AFFFFFF", "#007AFF") {
            startScanning()
        }
        val connectSelectedBtn = createButton("Connect Selected", "#007AFF", "#FFFFFF") {
            val position = spinner.selectedItemPosition
            if (position > 0 && position - 1 < discoveredDevices.size) {
                val device = discoveredDevices[position - 1]
                checkPermissionsAndConnect(device.address)
            } else {
                logView.append("\n[-] Select a discovered watch from list first.")
            }
        }
        val disconnectBtn = createButton("Disconnect", "#1AFFFFFF", "#FFFFFF") {
            stopScanning()
            bleManager.disconnect()
        }
        container.addView(createCard("CONNECTION", spinner, scanBtn, connectSelectedBtn, disconnectBtn))

        // 2. Settings Card
        val isNotificationAccessGranted = {
            val pkgName = packageName
            val flat = android.provider.Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
            flat != null && flat.contains(pkgName)
        }

        val promptForNotificationAccess = {
            android.app.AlertDialog.Builder(this@MainActivity)
                .setTitle("Notification Access Required")
                .setMessage("To read and send notifications to your watch, you must allow Notification Access.\n\nOn newer Android versions, you may first need to open App Info -> allow 'Restricted Settings' before enabling this permission.")
                .setPositiveButton("Go to Settings") { _, _ ->
                    startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"))
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        val prefs = getSharedPreferences("watch_prefs", Context.MODE_PRIVATE)
        if (!isNotificationAccessGranted() && !prefs.getBoolean("has_prompted_noti_access", false)) {
            promptForNotificationAccess()
            prefs.edit().putBoolean("has_prompted_noti_access", true).apply()
        }

        val callAlertCb = createCheckBox("Enable Bluetooth Calling", true, R.drawable.ic_bluetooth)
        val smsAlertCb = createCheckBox("Enable SMS Notifications", true, R.drawable.ic_message_square)
        val appAlertCb = createCheckBox("Enable App Notifications", true, R.drawable.ic_bell)
        
        val checkNotiPerms = android.widget.CompoundButton.OnCheckedChangeListener { cb, isChecked ->
            if (isChecked && !isNotificationAccessGranted()) {
                cb.isChecked = false
                promptForNotificationAccess()
            }
        }
        smsAlertCb.setOnCheckedChangeListener(checkNotiPerms)
        appAlertCb.setOnCheckedChangeListener(checkNotiPerms)
        
        val applySwitchesBtn = createButton("Sync Settings to Watch", "#1AFFFFFF", "#007AFF", R.drawable.ic_refresh_cw) {
            CoroutineScope(Dispatchers.IO).launch {
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 122, WatchProtocol.buildCallsSwitchPayload(callAlertCb.isChecked)))
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 124, WatchProtocol.buildAppSwitchPayload(appAlertCb.isChecked)))
                runOnUiThread { logView.append("\n[+] Notification switches updated & synced!") }
            }
        }
        container.addView(createCard("DEVICE SETTINGS", callAlertCb, smsAlertCb, appAlertCb, applySwitchesBtn))

        // 3. Health & GPS
        val syncWeatherBtn = createButton("Update Location & Weather", "#1AFFFFFF", "#007AFF", R.drawable.ic_cloud_sun) {
            val permissions = arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
            if (missing.isNotEmpty()) {
                ActivityCompat.requestPermissions(this, missing.toTypedArray(), 4)
            } else {
                WeatherManager.syncWeather(this@MainActivity, bleManager)
                logView.append("\n[*] Manual Weather & Location sync initiated...")
            }
        }
        container.addView(createCard("LOCATION & WEATHER", syncWeatherBtn))

        // 4. Contacts & Media
        val syncContactsBtn = createButton("Sync Contacts", "#1AFFFFFF", "#007AFF", R.drawable.ic_book_user) {
            val permissions = arrayOf(Manifest.permission.READ_CONTACTS)
            val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
            if (missing.isNotEmpty()) {
                ActivityCompat.requestPermissions(this, missing.toTypedArray(), 5)
            } else {
                val contacts = fetchPhoneContacts()
                if (contacts.isNotEmpty()) {
                    val payloads = buildContactsPayloads(contacts)
                    CoroutineScope(Dispatchers.IO).launch {
                        for (payload in payloads) {
                            bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 135, payload))
                            kotlinx.coroutines.delay(400)
                        }
                    }
                }
            }
        }
        val pushMusicBtn = createButton("Push Track Metadata", "#1AFFFFFF", "#007AFF", R.drawable.ic_music) {
            bleManager.pushMusicMetadata("Apple Music", 15)
            logView.append("\n[+] Media metadata pushed.")
        }
        container.addView(createCard("MEDIA & CONTACTS", syncContactsBtn, pushMusicBtn))



        // 5. Console Output Card (Hidden mostly, but keeps UI clean)
        logView = TextView(this).apply {
            text = "Watchify Logs...\n"
            setTextColor(Color.parseColor("#FFFFFF"))
            textSize = 11f
            typeface = android.graphics.Typeface.MONOSPACE
            setPadding(16, 16, 16, 16)
        }
        val logScroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 400)
            addView(logView)
        }
        container.addView(createCard("DIAGNOSTICS", logScroll))

        // Developer Settings Button - Plain Link Style
        val btnDebug = Button(this).apply {
            text = "Developer Settings"
            setTextColor(Color.parseColor("#007AFF"))
            textSize = 17f
            typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
            background = null
            isAllCaps = false
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 16, 0, 48) }
            setPadding(0, 32, 0, 32)
            val chevron = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_chevron_right)
            chevron?.setBounds(0, 0, 48, 48)
            chevron?.setTint(Color.parseColor("#007AFF"))
            setCompoundDrawables(null, null, chevron, null)
            compoundDrawablePadding = 16
            setOnClickListener {
                startActivity(Intent(this@MainActivity, DebugActivity::class.java))
            }
        }
        container.addView(btnDebug)

        val bottomContent = LinearLayout(this).apply {
            id = View.generateViewId()
            layoutParams = android.widget.RelativeLayout.LayoutParams(android.widget.RelativeLayout.LayoutParams.MATCH_PARENT, android.widget.RelativeLayout.LayoutParams.WRAP_CONTENT)
            orientation = LinearLayout.HORIZONTAL
            setPadding(32, 32, 32, 48) // bottom padding for anchor
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#40000000")) // Overlay
                setStroke(2, Color.parseColor("#4DFFFFFF"))
                // Only top corners are rounded
                cornerRadii = floatArrayOf(64f, 64f, 64f, 64f, 0f, 0f, 0f, 0f)
            }

            
            val homeBtn = Button(this@MainActivity).apply {
                text = "Home"
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                setBackgroundColor(Color.TRANSPARENT)
                setTextColor(Color.WHITE)
                isAllCaps = false
                typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                val homeIcon = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_house)
                homeIcon?.setBounds(0, 0, 60, 60)
                homeIcon?.setTint(Color.WHITE)
                setCompoundDrawables(null, homeIcon, null, null)
            }
            
            val healthBtn = Button(this@MainActivity).apply {
                text = "Health"
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                setBackgroundColor(Color.TRANSPARENT)
                setTextColor(Color.parseColor("#8E8E93"))
                isAllCaps = false
                typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                val healthIcon = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_heart)
                healthIcon?.setBounds(0, 0, 60, 60)
                healthIcon?.setTint(Color.parseColor("#8E8E93"))
                setCompoundDrawables(null, healthIcon, null, null)
            }

            val analyticsBtn = Button(this@MainActivity).apply {
                text = "Analytics"
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                setBackgroundColor(Color.TRANSPARENT)
                setTextColor(Color.parseColor("#8E8E93"))
                isAllCaps = false
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                val analyticsIcon = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_activity)
                analyticsIcon?.setBounds(0, 0, 60, 60)
                analyticsIcon?.setTint(Color.parseColor("#8E8E93"))
                setCompoundDrawables(null, analyticsIcon, null, null)
            }

            homeBtn.setOnClickListener {
                homeScroll.visibility = View.VISIBLE
                healthScroll.visibility = View.GONE
                analyticsScroll.visibility = View.GONE
                homeBtn.setTextColor(Color.WHITE)
                healthBtn.setTextColor(Color.parseColor("#8E8E93"))
                analyticsBtn.setTextColor(Color.parseColor("#8E8E93"))
                homeBtn.compoundDrawables[1]?.setTint(Color.WHITE)
                healthBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
                analyticsBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
            }

            healthBtn.setOnClickListener {
                homeScroll.visibility = View.GONE
                healthScroll.visibility = View.VISIBLE
                analyticsScroll.visibility = View.GONE
                homeBtn.setTextColor(Color.parseColor("#8E8E93"))
                healthBtn.setTextColor(Color.WHITE)
                analyticsBtn.setTextColor(Color.parseColor("#8E8E93"))
                homeBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
                healthBtn.compoundDrawables[1]?.setTint(Color.WHITE)
                analyticsBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
            }
            
            analyticsBtn.setOnClickListener {
                homeScroll.visibility = View.GONE
                healthScroll.visibility = View.GONE
                analyticsScroll.visibility = View.VISIBLE
                homeBtn.setTextColor(Color.parseColor("#8E8E93"))
                healthBtn.setTextColor(Color.parseColor("#8E8E93"))
                analyticsBtn.setTextColor(Color.WHITE)
                homeBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
                healthBtn.compoundDrawables[1]?.setTint(Color.parseColor("#8E8E93"))
                analyticsBtn.compoundDrawables[1]?.setTint(Color.WHITE)
            }
            
            addView(homeBtn)
            addView(healthBtn)
            addView(analyticsBtn)
        }
        val bottomGlass = GlassView(this).apply {
            layoutParams = android.widget.RelativeLayout.LayoutParams(android.widget.RelativeLayout.LayoutParams.MATCH_PARENT, 0).apply {
                addRule(android.widget.RelativeLayout.ALIGN_TOP, bottomContent.id)
                addRule(android.widget.RelativeLayout.ALIGN_BOTTOM, bottomContent.id)
            }
        }
        val bottomBar = android.widget.RelativeLayout(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 0, 0, 0)
                gravity = android.view.Gravity.BOTTOM
            }
            elevation = 16f
            clipToOutline = true
            outlineProvider = object : android.view.ViewOutlineProvider() {
                override fun getOutline(view: View, outline: android.graphics.Outline) {
                    outline.setRoundRect(0, 0, view.width, view.height + 64, 64f) // Add height + 64 to avoid rounding bottom
                }
            }
            addView(bottomGlass)
            addView(bottomContent)
        }

        val mainRootLayout = FrameLayout(this).apply {
            addView(contentFrame)
            addView(headerLayout)
            addView(bottomBar)
        }

        headerGlass.targetView = contentFrame
        bottomGlass.targetView = contentFrame

        homeScroll.setOnScrollChangeListener { _, _, _, _, _ ->
            headerGlass.invalidate()
            bottomGlass.invalidate()
        }
        healthScroll.setOnScrollChangeListener { _, _, _, _, _ ->
            headerGlass.invalidate()
            bottomGlass.invalidate()
        }

        setContentView(mainRootLayout)
    }

    
    private fun createValueTextView(): TextView {
        return TextView(this@MainActivity).apply {
            text = "--"
            textSize = 20f
            setTextColor(Color.parseColor("#8E8E93"))
            typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
            gravity = android.view.Gravity.END or android.view.Gravity.CENTER_VERTICAL
        }
    }

    private fun createExpandableHealthCard(title: String, iconRes: Int, graphView: GraphView, syncOpcode: Int, valueTextView: TextView): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#40000000")) // Translucent Frosted
                setStroke(2, Color.parseColor("#4DFFFFFF"))
                cornerRadius = 48f
            }
            setPadding(32, 32, 32, 32)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 16, 0, 16)
            }
        }
        
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            
            val icon = android.widget.ImageView(this@MainActivity).apply {
                setImageResource(iconRes)
                setColorFilter(Color.parseColor("#007AFF"))
                layoutParams = LinearLayout.LayoutParams(64, 64).apply {
                    setMargins(0, 0, 32, 0)
                }
            }
            
            val titleText = TextView(this@MainActivity).apply {
                text = title
                textSize = 20f
                setTextColor(Color.WHITE)
                typeface = androidx.core.content.res.ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            
            addView(icon)
            addView(titleText)
            addView(valueTextView)
        }
        
        val detailsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            setPadding(0, 32, 0, 0)
            
            graphView.layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 400)
            addView(graphView)
            
            val syncBtn = createButton("Sync $title", "#1AFFFFFF", "#007AFF", iconRes) {
                kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
                    bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, syncOpcode, ByteArray(0)))
                }
            }
            addView(syncBtn)
        }
        
        card.setOnClickListener {
            if (detailsContainer.visibility == View.GONE) {
                detailsContainer.visibility = View.VISIBLE
            } else {
                detailsContainer.visibility = View.GONE
            }
        }
        
        card.addView(header)
        card.addView(detailsContainer)
        return card
    }

    private fun createCard(title: String, vararg views: View): LinearLayout {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#40000000")) // Translucent Frosted
                setStroke(2, Color.parseColor("#4DFFFFFF"))
                cornerRadius = 48f
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(32, 16, 32, 32) }
            elevation = 8f
        }
        
        val header = TextView(this).apply {
            text = title.uppercase()
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
            setPadding(0, 0, 0, 24)
            if (title == "DIAGNOSTICS") {
                val icon = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, R.drawable.ic_terminal)
                icon?.setBounds(0, 0, 40, 40)
                icon?.setTint(Color.parseColor("#8E8E93"))
                setCompoundDrawables(icon, null, null, null)
                compoundDrawablePadding = 16
            }
        }
        card.addView(header)
        
        for (view in views) {
            card.addView(view)
        }
        return card
    }

    private fun createCheckBox(textVal: String, checkedVal: Boolean, iconRes: Int? = null): CheckBox {
        return CheckBox(this).apply {
            text = textVal
            setTextColor(Color.WHITE)
            isChecked = checkedVal
            textSize = 16f
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 16, 0, 16) }
            if (iconRes != null) {
                val drawable = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, iconRes)
                drawable?.setBounds(0, 0, 60, 60)
                setCompoundDrawables(drawable, null, null, null)
                compoundDrawablePadding = 32
            }
        }
    }

    private fun createSpinner(items: List<String>): Spinner {
        return Spinner(this).apply {
            val arrayAdapter = object : ArrayAdapter<String>(this@MainActivity, android.R.layout.simple_spinner_item, items) {
                override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                    val v = super.getView(position, convertView, parent)
                    (v as TextView).setTextColor(Color.WHITE)
                    v.setPadding(0, 24, 0, 24)
                    return v
                }
                override fun getDropDownView(position: Int, convertView: View?, parent: ViewGroup): View {
                    val v = super.getDropDownView(position, convertView, parent)
                    (v as TextView).setTextColor(Color.WHITE)
                    v.setBackgroundColor(Color.parseColor("#1C1C1E"))
                    v.setPadding(32, 32, 32, 32)
                    return v
                }
            }
            arrayAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            adapter = arrayAdapter
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 16, 0, 16) }
        }
    }

    private fun createButton(label: String, customColor: String? = null, customTextColor: String? = null, iconRes: Int? = null, onClick: () -> Unit): Button {
        return Button(this).apply {
            text = label
            setTextColor(Color.parseColor(customTextColor ?: "#FFFFFF"))
            textSize = 16f
            typeface = ResourcesCompat.getFont(this@MainActivity, R.font.sf_pro_bold)
            background = GradientDrawable().apply {
                setColor(Color.parseColor(customColor ?: "#007AFF"))
                if (customColor == "#1AFFFFFF") {
                    setStroke(2, Color.parseColor("#33FFFFFF")) // Give secondary glass buttons a border
                }
                cornerRadius = 32f
            }
            isAllCaps = false
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 16, 0, 16) }
            setPadding(64, 48, 64, 48)
            
            if (iconRes != null) {
                gravity = android.view.Gravity.CENTER_VERTICAL or android.view.Gravity.START
                val drawable = androidx.core.content.ContextCompat.getDrawable(this@MainActivity, iconRes)
                drawable?.setBounds(0, 0, 64, 64)
                setCompoundDrawables(drawable, null, null, null)
                compoundDrawablePadding = 48
            } else {
                gravity = android.view.Gravity.CENTER
            }
            setOnClickListener { onClick() }
        }
    }

    private fun checkPermissionsAndConnect(mac: String) {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }

        val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1)
        } else {
            bleManager.connect(mac)
        }
    }

    private fun geolocateIp() {
        runOnUiThread { logView.append("\n[*] Contacting geolocator...") }
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val urlConnection = URL("http://ip-api.com/json").openConnection() as HttpURLConnection
                urlConnection.connectTimeout = 3000
                urlConnection.readTimeout = 3000
                val text = urlConnection.inputStream.bufferedReader().use { it.readText() }
                val json = JSONObject(text)
                val lat = json.optDouble("lat", 40.7128)
                val lon = json.optDouble("lon", -74.0060)
                val city = json.optString("city", "New York")
                val country = json.optString("country", "US")
                
                val prefs = getSharedPreferences("watch_prefs", MODE_PRIVATE)
                prefs.edit().putFloat("last_lat", lat.toFloat()).putFloat("last_lon", lon.toFloat()).apply()
                
                val payload = WatchProtocol.buildGpsPayload(lat, lon)
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 140, payload))
                
                runOnUiThread {
                    logView.append("\n[+] IP Location Resolved: $city, $country (Lat: $lat, Lon: $lon)")
                }
            } catch (e: Exception) {
                runOnUiThread {
                    logView.append("\n[-] Geolocation Failed: ${e.message}. Using fallback (New York)")
                }
                val prefs = getSharedPreferences("watch_prefs", MODE_PRIVATE)
                prefs.edit().putFloat("last_lat", 40.7128f).putFloat("last_lon", -74.0060f).apply()
                val payload = WatchProtocol.buildGpsPayload(40.7128, -74.0060)
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 140, payload))
            }
        }
    }



    private fun updateConnectionStatus() {
        runOnUiThread {
            if (bleManager.isConnected()) {
                connectionBadge.text = "Connected"; connectionBadge.setTextColor(Color.parseColor("#34C759"))
                
            } else {
                connectionBadge.text = "Disconnected"; connectionBadge.setTextColor(Color.parseColor("#FF3B30"))
                
            }
        }
    }

    private fun fetchPhoneContacts(): List<Pair<String, String>> {
        val contacts = mutableListOf<Pair<String, String>>()
        val uri = android.provider.ContactsContract.CommonDataKinds.Phone.CONTENT_URI
        val projection = arrayOf(
            android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        
        try {
            contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numberIndex = cursor.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER)
                
                while (cursor.moveToNext()) {
                    val name = if (nameIndex >= 0) cursor.getString(nameIndex) ?: "" else ""
                    val number = if (numberIndex >= 0) cursor.getString(numberIndex) ?: "" else ""
                    val cleanNumber = number.filter { it.isDigit() || it == '+' }
                    
                    if (name.isNotEmpty() && cleanNumber.isNotEmpty()) {
                        contacts.add(Pair(name.take(30), cleanNumber.take(20)))
                    }
                }
            }
        } catch (e: Exception) {
            runOnUiThread { logView.append("\n[-] Error querying contacts: ${e.message}") }
        }
        return contacts.take(100)
    }

    private fun buildContactsPayloads(contacts: List<Pair<String, String>>): List<ByteArray> {
        val payloads = mutableListOf<ByteArray>()
        var bArr = ByteArray(2)
        var currentContactCount = 0
        var currentPackageIndex = 1

        for ((i, contact) in contacts.withIndex()) {
            val nameBytes = contact.first.toByteArray(Charsets.UTF_8)
            val nameLen = nameBytes.size
            val numStr = contact.second
            val numBytes = ByteArray(numStr.length) { numStr[it].code.toByte() }
            val numLen = numBytes.size

            val contactSize = 2 + nameLen + numLen
            val currentAccumulatedSize = bArr.size

            if (currentAccumulatedSize + contactSize > 220) {
                bArr[0] = currentPackageIndex.toByte()
                bArr[1] = currentContactCount.toByte()
                payloads.add(bArr)

                currentPackageIndex++
                bArr = ByteArray(2)
                currentContactCount = 0
            }

            val newAccumulatedSize = bArr.size + contactSize
            val bArr2 = ByteArray(newAccumulatedSize)
            System.arraycopy(bArr, 0, bArr2, 0, bArr.size)

            val idx = bArr.size
            bArr2[idx] = nameLen.toByte()
            System.arraycopy(nameBytes, 0, bArr2, idx + 1, nameLen)

            val idx2 = idx + 1 + nameLen
            bArr2[idx2] = numLen.toByte()
            System.arraycopy(numBytes, 0, bArr2, idx2 + 1, numLen)

            currentContactCount++
            bArr = bArr2

            if (i == contacts.size - 1) {
                bArr[0] = currentPackageIndex.toByte()
                bArr[1] = currentContactCount.toByte()
                payloads.add(bArr)
            }
        }
        return payloads
    }

    private var autoSyncJob: kotlinx.coroutines.Job? = null

    private fun startAutoSync() {
        if (autoSyncJob != null) return
        autoSyncJob = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            while (true) {
                kotlinx.coroutines.delay(60000)
                bleManager?.let {
                    if (it.isConnected()) {
                        runOnUiThread { logView.append("\n[*] Auto-syncing background data...") }
                        it.sendChunks(WatchProtocol.buildFastSyncRequests())
                    }
                }
            }
        }
    }
    
    override fun onDestroy() {
        autoSyncJob?.cancel()
        healthUpdateJob?.cancel()

        bleManager.unregisterLogCallback(logCallback)
        statusHandler.removeCallbacks(statusUpdater)
        super.onDestroy()
    }

    private fun startDriverServiceIfPermitted() {
        val serviceIntent = Intent(this, WatchDriverService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 100) {
            val allGranted = grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (allGranted || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED)) {
                startDriverServiceIfPermitted()
            } else {
                logView.append("\n[-] Missing critical Bluetooth/Location permissions. Watch sync will fail.")
            }
        }
    }
}
