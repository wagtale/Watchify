package com.watchify.app

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.Log
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.res.ResourcesCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class DebugActivity : AppCompatActivity() {

    private lateinit var bleManager: BleManager
    private lateinit var logConsole: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        
        val insetsController = androidx.core.view.WindowCompat.getInsetsController(window, window.decorView)
        insetsController.systemBarsBehavior = androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        insetsController.hide(androidx.core.view.WindowInsetsCompat.Type.navigationBars())
        
        bleManager = WatchApplication.instance.bleManager

        val sfPro = ResourcesCompat.getFont(this, R.font.sf_pro)
        val sfProBold = ResourcesCompat.getFont(this, R.font.sf_pro_bold)

        val rootLayout = ScrollView(this).apply {
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(
                    Color.parseColor("#000000"),
                    Color.parseColor("#0A1C3A"), // Very deep blue
                    Color.parseColor("#000000")
                )
            )
            isFillViewport = true
            clipToPadding = false
            isVerticalScrollBarEnabled = false
        }
        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(rootLayout) { view, windowInsets ->
            val insets = windowInsets.getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars())
            view.setPadding(0, insets.top + 120, 0, insets.bottom + 120)
            windowInsets
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 64, 32, 64)
        }
        rootLayout.addView(container)

        // Back Button
        val btnBack = TextView(this).apply {
            text = "‹ Back"
            setTextColor(Color.parseColor("#007AFF"))
            textSize = 17f
            typeface = sfPro
            setPadding(16, 16, 16, 16)
            setOnClickListener { finish() }
        }
        container.addView(btnBack)

        // Header Title
        val headerTitle = TextView(this).apply {
            text = "Developer Settings"
            setTextColor(Color.WHITE)
            textSize = 34f
            typeface = sfProBold
            setPadding(16, 0, 0, 32)
        }
        container.addView(headerTitle)

        // 1. Raw Command Card
        val commandCard = createCardContainer(this)
        val commandTitle = TextView(this).apply {
            text = "SEND RAW OPCODE"
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            isAllCaps = true
            typeface = sfProBold
            setPadding(16, 16, 16, 16)
        }
        commandCard.addView(commandTitle)

        val commandInput = EditText(this).apply {
            hint = "e.g., 20 (for battery)"
            setHintTextColor(Color.parseColor("#8E8E93"))
            setTextColor(Color.WHITE)
            typeface = sfPro
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setBackgroundColor(Color.TRANSPARENT)
            setPadding(16, 16, 16, 16)
        }
        commandCard.addView(commandInput)

        val btnSendRaw = createButton("Send Opcode") {
            val op = commandInput.text.toString().toIntOrNull()
            if (op != null) {
                CoroutineScope(Dispatchers.IO).launch {
                    val packets = WatchProtocol.buildMasterPacket(0, 1, op, ByteArray(0))
                    bleManager.sendChunks(packets)
                }
                appendLog("Sent opcode: $op")
            } else {
                appendLog("Invalid opcode")
            }
        }
        commandCard.addView(btnSendRaw)
        container.addView(commandCard)

        // 2. Watch Face Simulator Card
        val faceCard = createCardContainer(this)
        val faceTitle = TextView(this).apply {
            text = "EXPERIMENTAL"
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            isAllCaps = true
            typeface = sfProBold
            setPadding(16, 16, 16, 16)
        }
        faceCard.addView(faceTitle)

        val btnWatchFace = createButton("Push Custom Watch Face", "#007AFF", "#FFFFFF") {
            appendLog("Executing Watch Face push (Opcode 131)...")
            appendLog("WARNING: ParTool compression missing. Bypassing upload to prevent bricking.")
            // Logic would go here to chunk the file and send Opcode 131.
        }
        faceCard.addView(btnWatchFace)
        container.addView(faceCard)

        // 3. System Tools Card
        val systemCard = createCardContainer(this)
        val systemTitle = TextView(this).apply {
            text = "SYSTEM TOOLS"
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            isAllCaps = true
            typeface = sfProBold
            setPadding(16, 16, 16, 16)
        }
        systemCard.addView(systemTitle)

        val btnPoll = createButton("Poll Proprietary Opcode 2", "#1AFFFFFF", "#FF3B30") {
            appendLog("[*] Requesting Proprietary Device Info (Opcode 2)...")
            CoroutineScope(Dispatchers.IO).launch {
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 3, 2, ByteArray(0)))
            }
        }
        val btnPollStandard = createButton("Query Native BLE Chipset", "#1AFFFFFF", "#FF9500") {
            appendLog("[*] Requesting Standard BLE Device Profile...")
            bleManager.readStandardDeviceStrings()
        }
        val btnDump = createButton("Dump Logs to File", "#1AFFFFFF", "#007AFF") {
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val process = Runtime.getRuntime().exec("logcat -d -v time")
                    val logs = process.inputStream.bufferedReader().use { it.readText() }
                    val dir = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
                    val file = java.io.File(dir, "watchify_logs_${System.currentTimeMillis()}.txt")
                    file.writeText(logs)
                    runOnUiThread {
                        android.widget.Toast.makeText(this@DebugActivity, "Logcat saved to Downloads", android.widget.Toast.LENGTH_LONG).show()
                        appendLog("[+] Dumped to: ${file.name}")
                    }
                } catch (e: Exception) {
                    runOnUiThread { appendLog("[-] Dump failed: ${e.message}") }
                }
            }
        }
        systemCard.addView(btnPoll)
        systemCard.addView(btnPollStandard)
        systemCard.addView(btnDump)
        container.addView(systemCard)

        // Experimental Commands
        val expCard = createCardContainer(this)
        val expTitle = TextView(this).apply {
            text = "EXPERIMENTAL COMMANDS"
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            isAllCaps = true
            typeface = sfProBold
            setPadding(16, 16, 16, 16)
        }
        expCard.addView(expTitle)

        val timeSyncBtn = createButton("Force Time Sync", "#1AFFFFFF", "#007AFF") {
            CoroutineScope(Dispatchers.IO).launch {
                bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 1, 104, WatchProtocol.getTimeSyncPayload()))
                runOnUiThread { appendLog("\n[+] Force Time Sync Pushed") }
            }
        }
        
        var isFindingWatch = false
        val findWatchBtn = createButton("Find My Watch", "#1AFFFFFF", "#007AFF") {
            isFindingWatch = !isFindingWatch
            CoroutineScope(Dispatchers.IO).launch {
                bleManager.sendChunks(WatchProtocol.buildFindDevicePacket(isFindingWatch))
                runOnUiThread { 
                    appendLog(if (isFindingWatch) "\n[*] Sending Find Watch signal..." else "\n[*] Stopped Find Watch signal.") 
                }
            }
        }

        val prefs = getSharedPreferences("watch_prefs", Context.MODE_PRIVATE)
        val cityInput = android.widget.EditText(this).apply {
            hint = "City for Weather (e.g. London)"
            setHintTextColor(Color.GRAY)
            setTextColor(Color.WHITE)
            setText(prefs.getString("weather_city", ""))
            setPadding(32, 32, 32, 32)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#1C1C1E"))
                cornerRadius = 16f
            }
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                setMargins(0, 0, 0, 16)
            }
        }

        val setRegionSyncWeatherBtn = createButton("Set Region & Sync Weather", "#1AFFFFFF", "#007AFF") {
            val city = cityInput.text.toString().trim()
            prefs.edit().putString("weather_city", city).apply()
            WeatherManager.syncWeather(this@DebugActivity, bleManager)
            appendLog("\n[+] Set weather region to '$city' and syncing...")
        }

        expCard.addView(timeSyncBtn)
        expCard.addView(findWatchBtn)
        expCard.addView(cityInput)
        expCard.addView(setRegionSyncWeatherBtn)
        container.addView(expCard)

        // 3. Live Logs
        val logCard = createCardContainer(this)
        val logTitle = TextView(this).apply {
            text = "BLE LOG CONSOLE"
            setTextColor(Color.parseColor("#8E8E93"))
            textSize = 12f
            isAllCaps = true
            typeface = sfProBold
            setPadding(16, 16, 16, 16)
        }
        logCard.addView(logTitle)

        logConsole = TextView(this).apply {
            setTextColor(Color.parseColor("#FFFFFF")) // Replaced green with white for logs
            textSize = 10f
            typeface = android.graphics.Typeface.MONOSPACE
            setPadding(16, 16, 16, 16)
            maxLines = 20
            text = "> Debug console initialized.\n"
        }
        logCard.addView(logConsole)
        container.addView(logCard)

        bleManager.registerLogCallback { msg ->
            runOnUiThread { appendLog(msg) }
        }

        setContentView(rootLayout)
    }

    private fun appendLog(msg: String) {
        if (logConsole.lineCount > 20) {
            val currentText = logConsole.text.toString()
            val newlineIndex = currentText.indexOf('\n')
            if (newlineIndex != -1) {
                logConsole.text = currentText.substring(newlineIndex + 1)
            }
        }
        logConsole.append(msg + "\n")
    }

    override fun onDestroy() {
        super.onDestroy()
        bleManager.registerLogCallback { }
    }

    private fun createCardContainer(context: Context): LinearLayout {
        val card = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#1AFFFFFF"))
                setStroke(2, Color.parseColor("#33FFFFFF"))
                cornerRadius = 32f
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, 16, 0, 32) }
            setPadding(16, 16, 16, 16)
        }
        return card
    }

    private fun createButton(label: String, customColor: String? = null, customTextColor: String? = null, onClick: () -> Unit): Button {
        return Button(this).apply {
            text = label
            setTextColor(Color.parseColor(customTextColor ?: "#FFFFFF"))
            textSize = 16f
            typeface = ResourcesCompat.getFont(context, R.font.sf_pro_bold)
            background = GradientDrawable().apply {
                setColor(Color.parseColor(customColor ?: "#007AFF"))
                if (customColor == "#1AFFFFFF") {
                    setStroke(2, Color.parseColor("#33FFFFFF")) // Give secondary glass buttons a border
                }
                cornerRadius = 24f
            }
            isAllCaps = false
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(16, 16, 16, 16) }
            setPadding(0, 32, 0, 32)
            setOnClickListener { onClick() }
        }
    }
}
