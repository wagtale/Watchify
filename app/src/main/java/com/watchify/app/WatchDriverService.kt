package com.watchify.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*

class WatchDriverService : Service() {

    private var mediaPlayer: MediaPlayer? = null
    
    private val driverReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                "com.watchify.app.FIND_PHONE_START" -> playAlarm()
                "com.watchify.app.FIND_PHONE_STOP" -> stopAlarm()
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForegroundService()
        
        val filter = IntentFilter()
        filter.addAction("com.watchify.app.FIND_PHONE_START")
        filter.addAction("com.watchify.app.FIND_PHONE_STOP")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(driverReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(driverReceiver, filter)
        }
    }

    private var weatherJob: Job? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundService()
        startWeatherSync()
        if (!WatchApplication.instance.bleManager.isConnected()) {
            WatchApplication.instance.bleManager.attemptAutoConnect()
        }
        return START_STICKY
    }

    private fun startWeatherSync() {
        weatherJob?.cancel()
        weatherJob = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                if (WatchApplication.instance.bleManager.isConnected()) {
                    WeatherManager.syncWeather(this@WatchDriverService, WatchApplication.instance.bleManager)
                    // Request battery every 5 mins in background
                    WatchApplication.instance.bleManager.sendChunks(WatchProtocol.buildMasterPacket(0, 3, 3, ByteArray(0)))
                }
                delay(5 * 60 * 1000L) // 5 minutes
            }
        }
    }

    private fun playAlarm() {
        if (mediaPlayer == null) {
            val alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM) ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            mediaPlayer = MediaPlayer().apply {
                setDataSource(this@WatchDriverService, alarmUri)
                setAudioStreamType(AudioManager.STREAM_ALARM)
                isLooping = true
                prepare()
            }
        }
        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audioManager.setStreamVolume(AudioManager.STREAM_ALARM, audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
        mediaPlayer?.start()
    }

    private fun stopAlarm() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
    }

    override fun onDestroy() {
        weatherJob?.cancel()
        stopAlarm()
        unregisterReceiver(driverReceiver)
        super.onDestroy()
    }

    private fun startForegroundService() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (androidx.core.content.ContextCompat.checkSelfPermission(this, android.Manifest.permission.BLUETOOTH_CONNECT) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                stopSelf()
                return
            }
        }
        val channelId = "watchify_driver_channel"
        val channelName = "Watchify Background Service"
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val chan = NotificationChannel(channelId, channelName, NotificationManager.IMPORTANCE_LOW)
            chan.lightColor = Color.BLUE
            chan.lockscreenVisibility = Notification.VISIBILITY_SECRET
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(chan)
        }

        val intent = Intent(this, MainActivity::class.java)
        val pendingIntentFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        } else {
            PendingIntent.FLAG_UPDATE_CURRENT
        }
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, pendingIntentFlags)

        val notificationBuilder = NotificationCompat.Builder(this, channelId)
        val notification = notificationBuilder.setOngoing(true)
            .setContentTitle("Watchify is running")
            .setContentText("Maintaining connection to your smart watch")
            .setPriority(NotificationManager.IMPORTANCE_LOW)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setContentIntent(pendingIntent)
            .build()

        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(2, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } else {
            startForeground(2, notification)
        }
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}
