package com.watchify.app

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.service.notification.NotificationListenerService.RankingMap
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import android.media.session.MediaSessionManager
import android.media.session.MediaController
import android.media.session.PlaybackState
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.content.ComponentName
import android.media.AudioManager
import android.content.Context

class NotificationMonitor : NotificationListenerService() {

    private var mediaSessionManager: MediaSessionManager? = null
    private val controllerCallbacks = mutableMapOf<MediaController, MediaController.Callback>()
    
    private var lastNotificationHash = 0
    private var lastNotificationTime = 0L

    companion object {
        private var activeController: MediaController? = null

        fun getActiveController(): MediaController? {
            return activeController
        }

        fun getCurrentTrackInfo(): String {
            val controller = activeController ?: return "No Active Media"
            val metadata = controller.metadata ?: return "Unknown Track"
            val title = metadata.getString(MediaMetadata.METADATA_KEY_TITLE) ?: "Unknown Track"
            val artist = metadata.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: "Unknown Artist"
            return "$title - $artist"
        }

        fun getCurrentVolume(context: Context): Int {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val currentVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
            val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            return (currentVolume * 15) / if (maxVolume > 0) maxVolume else 15
        }
        
        fun updateActiveController(controller: MediaController?) {
            activeController = controller
        }
    }

    override fun onCreate() {
        super.onCreate()
        Log.d("NotificationMonitor", "NotificationMonitor service created.")
        mediaSessionManager = getSystemService(Context.MEDIA_SESSION_SERVICE) as? MediaSessionManager
        
        try {
            mediaSessionManager?.addOnActiveSessionsChangedListener({ controllers ->
                updateMediaControllers(controllers)
            }, ComponentName(this, NotificationMonitor::class.java))
            
            val initialControllers = mediaSessionManager?.getActiveSessions(ComponentName(this, NotificationMonitor::class.java))
            if (initialControllers != null) {
                updateMediaControllers(initialControllers)
            }
        } catch (e: SecurityException) {
            Log.e("NotificationMonitor", "No permission to get active sessions: ${e.message}")
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        handleNotification(sbn)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?, rankingMap: RankingMap?) {
        super.onNotificationPosted(sbn, rankingMap)
        handleNotification(sbn)
    }

    private fun handleNotification(sbn: StatusBarNotification?) {
        if (sbn == null) return
        Log.d("NotificationMonitor", "Received notification: package=${sbn.packageName}")
        
        val ble = WatchApplication.instance.bleManager
        if (!ble.isConnected()) {
            Log.d("NotificationMonitor", "BleManager is disconnected, ignoring notification")
            return
        }

        // Ignore ongoing system notifications (e.g. music players, GPS, charging alerts)
        if (sbn.isOngoing || (sbn.notification.flags and android.app.Notification.FLAG_GROUP_SUMMARY != 0)) {
            Log.d("NotificationMonitor", "Ignoring ongoing or group summary notification")
            return
        }

        val packageName = sbn.packageName
        val extras = sbn.notification.extras
        val title = extras.getString("android.title") ?: extras.getCharSequence("android.title")?.toString() ?: ""
        val body = extras.getCharSequence("android.text")?.toString() ?: extras.getString("android.text") ?: ""

        if (title.isEmpty() && body.isEmpty()) {
            Log.d("NotificationMonitor", "Title and Body are both empty, ignoring")
            return
        }

        val appName = try {
            val pm = packageManager
            val ai = pm.getApplicationInfo(packageName, 0)
            pm.getApplicationLabel(ai).toString()
        } catch (e: Exception) {
            packageName.substringAfterLast(".").replaceFirstChar { if (it.isLowerCase()) it.titlecase(java.util.Locale.getDefault()) else it.toString() }
        }

        val appId = when {
            packageName.contains("dialer") || packageName.contains("telecom") -> 1 // Calls
            packageName.contains("mms") || packageName.contains("sms") || packageName.contains("messaging") -> 2 // SMS
            packageName.contains("mobileqq") -> 3 // QQ
            packageName.contains("tencent.mm") -> 4 // WeChat
            packageName.contains("gmail") || packageName.contains("email") || packageName.contains("outlook") -> 5 // MAIL
            packageName.contains("facebook.katana") || packageName.contains("facebook.orca") -> 6 // Facebook
            packageName.contains("twitter") || packageName.contains("x.android") -> 7 // Twitter
            packageName.contains("whatsapp") -> 8 // WhatsApp
            packageName.contains("instagram") -> 9 // Instagram
            packageName.contains("skype") -> 10 // Skype
            packageName.contains("linkedin") -> 11 // LinkedIn
            packageName.contains("line") -> 12 // Line
            else -> 13 // OTHER — generic notification icon (not LINE)
        }

        val displayTitle = if (appId >= 13) appName else title
        val displayBody = if (appId >= 13) {
            if (title.isNotEmpty() && title != appName) "$title: $body" else body
        } else {
            body
        }
        
        val currentHash = (displayTitle + displayBody).hashCode()
        val currentTime = System.currentTimeMillis()
        if (currentHash == lastNotificationHash && (currentTime - lastNotificationTime) < 3000) {
            Log.d("NotificationMonitor", "Ignoring duplicate notification within 3 seconds")
            return
        }
        lastNotificationHash = currentHash
        lastNotificationTime = currentTime

        if (BuildConfig.DEBUG) {
            Log.d("NotificationMonitor", "Intercepted [$packageName] -> AppId $appId: $displayTitle - $displayBody")
        }

        // Send over BLE on a background coroutine
        CoroutineScope(Dispatchers.IO).launch {
            val payload = WatchProtocol.buildNoticePayload(appId, displayTitle, displayBody)
            val packets = WatchProtocol.buildMasterPacket(0, 1, 107, payload)
            ble.sendChunks(packets)
        }
    }

    private fun updateMediaControllers(controllers: List<MediaController>?) {
        if (controllers == null) return
        Log.d("NotificationMonitor", "updateMediaControllers: ${controllers.size} controllers found")
        
        // Unregister old callbacks
        for ((controller, callback) in controllerCallbacks) {
            try {
                controller.unregisterCallback(callback)
            } catch (e: Exception) {}
        }
        controllerCallbacks.clear()

        // Set the primary active controller to the first one in the list
        val primaryController = controllers.firstOrNull()
        updateActiveController(primaryController)

        if (primaryController != null) {
            Log.d("NotificationMonitor", "Tracking primary media controller: ${primaryController.packageName}")
            // Register callback to listen to metadata and state changes
            val callback = object : MediaController.Callback() {
                override fun onMetadataChanged(metadata: MediaMetadata?) {
                    super.onMetadataChanged(metadata)
                    val track = getCurrentTrackInfo()
                    val vol = getCurrentVolume(this@NotificationMonitor)
                    Log.d("NotificationMonitor", "Media metadata changed: $track")
                    CoroutineScope(Dispatchers.IO).launch {
                        WatchApplication.instance.bleManager.pushMusicMetadata(track, vol)
                    }
                }

                override fun onPlaybackStateChanged(state: PlaybackState?) {
                    super.onPlaybackStateChanged(state)
                    val track = getCurrentTrackInfo()
                    val vol = getCurrentVolume(this@NotificationMonitor)
                    CoroutineScope(Dispatchers.IO).launch {
                        WatchApplication.instance.bleManager.pushMusicMetadata(track, vol)
                    }
                }
            }
            primaryController.registerCallback(callback)
            controllerCallbacks[primaryController] = callback

            // Push initial info to watch immediately
            val track = getCurrentTrackInfo()
            val vol = getCurrentVolume(this)
            CoroutineScope(Dispatchers.IO).launch {
                WatchApplication.instance.bleManager.pushMusicMetadata(track, vol)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // Clean up callbacks
        for ((controller, callback) in controllerCallbacks) {
            try {
                controller.unregisterCallback(callback)
            } catch (e: Exception) {}
        }
        controllerCallbacks.clear()
        updateActiveController(null)
    }
}
