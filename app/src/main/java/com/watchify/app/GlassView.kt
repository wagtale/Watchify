package com.watchify.app

import android.content.Context
import android.graphics.*
import android.os.Build
import android.view.View

/**
 * GlassView — smooth frosted-glass overlay.
 *
 * API 31+: GPU-accelerated RenderEffect blur of the view's own semi-transparent
 *          tinted fill. Frame-synchronous, zero lag, no async callbacks.
 * API <31: Plain semi-transparent dark overlay — clean and glitch-free.
 */
class GlassView(context: Context) : View(context) {

    private val cornerRadius = 26f * resources.displayMetrics.density
    private val clipPath = Path()
    private val boundsF = RectF()

    // The tinted fill that gets blurred on API 31+.
    // Slightly warm dark — matches the app's dark chrome.
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(160, 18, 18, 24)
    }

    init {
        setLayerType(LAYER_TYPE_HARDWARE, null)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            setRenderEffect(
                RenderEffect.createBlurEffect(50f, 50f, Shader.TileMode.CLAMP)
            )
        }
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        boundsF.set(0f, 0f, w.toFloat(), h.toFloat())
        clipPath.reset()
        clipPath.addRoundRect(boundsF, cornerRadius, cornerRadius, Path.Direction.CW)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.save()
        canvas.clipPath(clipPath)
        canvas.drawRoundRect(boundsF, cornerRadius, cornerRadius, fillPaint)
        canvas.restore()
    }
}
