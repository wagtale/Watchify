package com.watchify.app

import android.app.Application
import android.util.Log

class WatchApplication : Application() {
    lateinit var bleManager: BleManager
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        Log.d("WatchApplication", "UtraLink Application Initialized.")
        
        bleManager = BleManager(this)
        
        // Auto-connect on application startup if a MAC address was saved
        bleManager.attemptAutoConnect()
    }

    companion object {
        lateinit var instance: WatchApplication
            private set
    }
}
