package com.watchify.app

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Camera
import android.os.Bundle
import android.os.Environment
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.Toast
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class CameraActivity : Activity(), SurfaceHolder.Callback {

    companion object {
        const val ACTION_TAKE_PHOTO = "com.zk.watch.ACTION_TAKE_PHOTO"
        const val ACTION_CLOSE_CAMERA = "com.zk.watch.ACTION_CLOSE_CAMERA"
    }

    private var camera: Camera? = null
    private var surfaceView: SurfaceView? = null
    private var surfaceHolder: SurfaceHolder? = null
    private var isPreviewRunning = false

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                ACTION_TAKE_PHOTO -> takePhoto()
                ACTION_CLOSE_CAMERA -> finish()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Simple Fullscreen preview layout
        val frameLayout = FrameLayout(this)
        frameLayout.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )

        surfaceView = SurfaceView(this)
        surfaceView?.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        frameLayout.addView(surfaceView)
        setContentView(frameLayout)

        surfaceHolder = surfaceView?.holder
        surfaceHolder?.addCallback(this)

        val filter = IntentFilter().apply {
            addAction(ACTION_TAKE_PHOTO)
            addAction(ACTION_CLOSE_CAMERA)
        }
        
        androidx.core.content.ContextCompat.registerReceiver(
            this,
            receiver,
            filter,
            androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    private fun takePhoto() {
        if (camera == null) return
        try {
            camera?.takePicture(
                Camera.ShutterCallback {
                    // System plays default shutter sound
                },
                null,
                Camera.PictureCallback { data, cam ->
                    savePhoto(data)
                    // Restart preview so camera is ready for another shot
                    try {
                        cam.startPreview()
                    } catch (e: Exception) {}
                }
            )
        } catch (e: Exception) {
            Toast.makeText(this, "Capture error: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun savePhoto(data: ByteArray) {
        try {
            val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM), "ZKWatch")
            if (!dir.exists()) {
                dir.mkdirs()
            }
            val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val file = File(dir, "IMG_$timeStamp.jpg")
            val fos = FileOutputStream(file)
            fos.write(data)
            fos.close()
            
            // Scan media library to reflect new image in Gallery app immediately
            val mediaScanIntent = Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE)
            mediaScanIntent.data = android.net.Uri.fromFile(file)
            sendBroadcast(mediaScanIntent)

            Toast.makeText(this, "Saved: ${file.absolutePath}", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(this, "Failed to save photo: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    override fun surfaceCreated(holder: SurfaceHolder) {
        try {
            camera = Camera.open()
            camera?.setDisplayOrientation(90) // Match Portrait orientation
            camera?.setPreviewDisplay(holder)
        } catch (e: Exception) {
            Toast.makeText(this, "Camera preview open failed: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        if (isPreviewRunning) {
            camera?.stopPreview()
            isPreviewRunning = false
        }
        if (camera != null) {
            try {
                val params = camera?.parameters
                if (params?.supportedFocusModes?.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE) == true) {
                    params.focusMode = Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE
                }
                camera?.parameters = params
                
                camera?.startPreview()
                isPreviewRunning = true
            } catch (e: Exception) {}
        }
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        camera?.stopPreview()
        camera?.release()
        camera = null
        isPreviewRunning = false
    }

    override fun onDestroy() {
        try {
            unregisterReceiver(receiver)
        } catch (e: Exception) {}
        super.onDestroy()
    }
}
