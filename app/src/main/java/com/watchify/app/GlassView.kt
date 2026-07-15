package com.watchify.app

import android.app.Activity
import android.content.Context
import android.graphics.*
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.PixelCopy
import android.view.View

/**
 * GlassView — clean frosted-glass blur of real content behind the view.
 * No shimmer, no specular, no border. Just blur.
 */
class GlassView(context: Context) : View(context) {

    private val blurRadius = 12          // ~50 % of the heavy blur; feels natural not excessive
    private val debounceMs = 120L

    private val clipPath = Path()
    private val boundsF = RectF()
    private val cornerRadius = 26f * resources.displayMetrics.density

    private var blurBitmap: Bitmap? = null
    private val blurPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { isFilterBitmap = true }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var captureRunnable: Runnable? = null
    private var captureInProgress = false

    init { setLayerType(LAYER_TYPE_HARDWARE, null) }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (w == 0 || h == 0) return
        boundsF.set(0f, 0f, w.toFloat(), h.toFloat())
        clipPath.reset()
        clipPath.addRoundRect(boundsF, cornerRadius, cornerRadius, Path.Direction.CW)
        invalidateBlur()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.save()
        canvas.clipPath(clipPath)
        val bmp = blurBitmap
        if (bmp != null && !bmp.isRecycled) {
            canvas.drawBitmap(bmp, 0f, 0f, blurPaint)
        } else {
            // Pre-capture fallback — solid dark tint
            canvas.drawColor(Color.argb(120, 18, 18, 22))
        }
        canvas.restore()
    }

    // -----------------------------------------------------------------------

    fun invalidateBlur() {
        captureRunnable?.let { mainHandler.removeCallbacks(it) }
        val r = Runnable { performCapture() }
        captureRunnable = r
        mainHandler.postDelayed(r, debounceMs)
    }

    private fun performCapture() {
        if (width == 0 || height == 0 || captureInProgress) return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val window = (context as? Activity)?.window ?: return

        val loc = IntArray(2); getLocationInWindow(loc)
        val dv = window.decorView
        val rect = Rect(
            loc[0].coerceAtLeast(0),
            loc[1].coerceAtLeast(0),
            (loc[0] + width).coerceAtMost(dv.width),
            (loc[1] + height).coerceAtMost(dv.height)
        )
        if (rect.isEmpty) return

        val dest = Bitmap.createBitmap(rect.width(), rect.height(), Bitmap.Config.ARGB_8888)
        captureInProgress = true
        PixelCopy.request(window, rect, dest, { result ->
            captureInProgress = false
            if (result == PixelCopy.SUCCESS) {
                Thread {
                    val blurred = blur(dest, blurRadius)
                    dest.recycle()
                    mainHandler.post {
                        blurBitmap?.recycle()
                        blurBitmap = blurred
                        invalidate()
                    }
                }.start()
            } else dest.recycle()
        }, mainHandler)
    }

    /** 3-pass box blur ≈ Gaussian, O(w·h) per pass. */
    private fun blur(src: Bitmap, r: Int): Bitmap {
        val w = src.width; val h = src.height
        val px = IntArray(w * h)
        src.getPixels(px, 0, w, 0, 0, w, h)
        repeat(3) { blurH(px, w, h, r); blurV(px, w, h, r) }
        val out = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        out.setPixels(px, 0, w, 0, 0, w, h)
        return out
    }

    private fun blurH(px: IntArray, w: Int, h: Int, r: Int) {
        val div = (r + r + 1).toFloat()
        for (y in 0 until h) {
            val base = y * w
            var rs = 0; var gs = 0; var bs = 0
            for (dx in -r..r) { val p = px[base + dx.coerceIn(0, w-1)]; rs += (p shr 16) and 0xFF; gs += (p shr 8) and 0xFF; bs += p and 0xFF }
            for (x in 0 until w) {
                px[base + x] = (0xFF shl 24) or ((rs/div).toInt() shl 16) or ((gs/div).toInt() shl 8) or (bs/div).toInt()
                val a = px[base + (x+r+1).coerceIn(0,w-1)]; val b = px[base + (x-r).coerceIn(0,w-1)]
                rs += ((a shr 16) and 0xFF) - ((b shr 16) and 0xFF)
                gs += ((a shr 8) and 0xFF) - ((b shr 8) and 0xFF)
                bs += (a and 0xFF) - (b and 0xFF)
            }
        }
    }

    private fun blurV(px: IntArray, w: Int, h: Int, r: Int) {
        val div = (r + r + 1).toFloat()
        for (x in 0 until w) {
            var rs = 0; var gs = 0; var bs = 0
            for (dy in -r..r) { val p = px[dy.coerceIn(0,h-1)*w+x]; rs += (p shr 16) and 0xFF; gs += (p shr 8) and 0xFF; bs += p and 0xFF }
            for (y in 0 until h) {
                px[y*w+x] = (0xFF shl 24) or ((rs/div).toInt() shl 16) or ((gs/div).toInt() shl 8) or (bs/div).toInt()
                val a = px[(y+r+1).coerceIn(0,h-1)*w+x]; val b = px[(y-r).coerceIn(0,h-1)*w+x]
                rs += ((a shr 16) and 0xFF) - ((b shr 16) and 0xFF)
                gs += ((a shr 8) and 0xFF) - ((b shr 8) and 0xFF)
                bs += (a and 0xFF) - (b and 0xFF)
            }
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        mainHandler.postDelayed({ invalidateBlur() }, 300)
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        mainHandler.removeCallbacksAndMessages(null)
        blurBitmap?.recycle()
        blurBitmap = null
    }
}
