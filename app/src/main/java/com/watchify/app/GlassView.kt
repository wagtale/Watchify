package com.watchify.app

import android.animation.ValueAnimator
import android.app.Activity
import android.content.Context
import android.graphics.*
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.PixelCopy
import android.view.View
import android.view.animation.LinearInterpolator

/**
 * GlassView — Liquid Glass material for Android, inspired by iOS 26.
 *
 * Uses PixelCopy (API 26+) to capture the actual rendered pixels behind this view,
 * applies a fast multi-pass box blur, then composites the following layers on top:
 *
 *   1. Blurred real background capture  ← actual content behind, blurred
 *   2. Dark tinted frosted overlay       ← the "glass body"
 *   3. Top specular gradient             ← light glancing off the top edge
 *   4. Animated iridescent shimmer       ← slow prismatic sweep (very subtle)
 *   5. Bottom inner shadow               ← material depth
 *   6. Gradient border stroke            ← bright rim, brighter at top
 *
 * On API 25 and below, layers 2–6 are still rendered but without the real blur capture,
 * falling back to a semi-transparent dark overlay that still looks great.
 *
 * Call [invalidateBlur] from scroll listeners to keep the blur accurate as content moves.
 */
class GlassView(context: Context) : View(context) {

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------
    private val dp = resources.displayMetrics.density
    /** Corner radius — matches the parent RelativeLayout outline (64px / 2 inset = 32dp equivalent). */
    private val cornerRadius = 26f * dp
    /** Blur radius for the background capture. Increase for more frosted-glass look. */
    private val blurRadius = 22
    /** How long to wait after an invalidateBlur() call before re-capturing (debounce). */
    private val captureDebounceMs = 120L

    // -----------------------------------------------------------------------
    // Clipping
    // -----------------------------------------------------------------------
    private val clipPath = Path()
    private val boundsF = RectF()

    // -----------------------------------------------------------------------
    // Background blur
    // -----------------------------------------------------------------------
    private var blurBitmap: Bitmap? = null
    private val blurPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { isFilterBitmap = true }
    private val mainHandler = Handler(Looper.getMainLooper())
    private var captureRunnable: Runnable? = null
    private var captureInProgress = false

    // -----------------------------------------------------------------------
    // Glass body overlay  (dark tinted, semi-transparent)
    // -----------------------------------------------------------------------
    private val glassPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(48, 16, 16, 22)
    }

    // -----------------------------------------------------------------------
    // Specular top-edge highlight
    // -----------------------------------------------------------------------
    private val specularPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    // -----------------------------------------------------------------------
    // Bottom inner shadow
    // -----------------------------------------------------------------------
    private val innerShadowPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    // -----------------------------------------------------------------------
    // Animated iridescent shimmer
    // -----------------------------------------------------------------------
    private val shimmerPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var shimmerProgress = 0f
    private val shimmerAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = 5500L
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener {
            shimmerProgress = it.animatedValue as Float
            invalidate()
        }
    }

    // -----------------------------------------------------------------------
    // Border stroke
    // -----------------------------------------------------------------------
    private val borderPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 1.1f * dp
    }

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------
    init {
        // Hardware layer so RenderEffect (API 31+) and our Canvas ops are GPU-accelerated
        setLayerType(LAYER_TYPE_HARDWARE, null)
    }

    // -----------------------------------------------------------------------
    // Layout
    // -----------------------------------------------------------------------
    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (w == 0 || h == 0) return
        val wf = w.toFloat()
        val hf = h.toFloat()

        boundsF.set(0f, 0f, wf, hf)
        clipPath.reset()
        clipPath.addRoundRect(boundsF, cornerRadius, cornerRadius, Path.Direction.CW)

        // Specular: bright white → transparent, covering top ~40% of height
        specularPaint.shader = LinearGradient(
            0f, 0f,
            0f, hf * 0.40f,
            intArrayOf(Color.argb(105, 255, 255, 255), Color.argb(0, 255, 255, 255)),
            null,
            Shader.TileMode.CLAMP
        )

        // Inner shadow: transparent → dark, bottom 35%
        innerShadowPaint.shader = LinearGradient(
            0f, hf * 0.65f,
            0f, hf,
            intArrayOf(Color.argb(0, 0, 0, 0), Color.argb(52, 0, 0, 0)),
            null,
            Shader.TileMode.CLAMP
        )

        // Border: brighter at top, dimmer at mid, slightly brighter at bottom
        borderPaint.shader = LinearGradient(
            0f, 0f,
            0f, hf,
            intArrayOf(
                Color.argb(135, 255, 255, 255),
                Color.argb(38,  255, 255, 255),
                Color.argb(68,  255, 255, 255)
            ),
            floatArrayOf(0f, 0.5f, 1f),
            Shader.TileMode.CLAMP
        )

        invalidateBlur()
    }

    // -----------------------------------------------------------------------
    // Drawing
    // -----------------------------------------------------------------------
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w == 0f || h == 0f) return

        canvas.save()
        canvas.clipPath(clipPath)

        // Layer 1: Real blurred background (what's physically behind this glass)
        val bmp = blurBitmap
        if (bmp != null && !bmp.isRecycled) {
            canvas.drawBitmap(bmp, 0f, 0f, blurPaint)
        }

        // Layer 2: Dark tinted glass body overlay
        canvas.drawRoundRect(boundsF, cornerRadius, cornerRadius, glassPaint)

        // Layer 3: Top specular highlight
        canvas.drawRoundRect(boundsF, cornerRadius, cornerRadius, specularPaint)

        // Layer 4: Iridescent shimmer
        drawShimmer(canvas, w, h)

        // Layer 5: Bottom inner shadow
        canvas.drawRoundRect(boundsF, cornerRadius, cornerRadius, innerShadowPaint)

        // Layer 6: Border stroke
        val inset = borderPaint.strokeWidth / 2f
        canvas.drawRoundRect(
            inset, inset, w - inset, h - inset,
            (cornerRadius - inset).coerceAtLeast(0f),
            (cornerRadius - inset).coerceAtLeast(0f),
            borderPaint
        )

        canvas.restore()
    }

    private fun drawShimmer(canvas: Canvas, w: Float, h: Float) {
        // Diagonal shimmer sweep: faint iridescent band moves left→right on loop
        val sweep = w * 2.2f
        val x = (shimmerProgress * (w + sweep)) - sweep * 0.5f

        shimmerPaint.shader = LinearGradient(
            x - sweep * 0.4f, 0f,
            x + sweep * 0.6f, h,
            intArrayOf(
                Color.argb(0,   255, 255, 255),
                Color.argb(7,   155, 210, 255),  // icy blue
                Color.argb(16,  255, 255, 255),  // white peak
                Color.argb(7,   255, 168, 218),  // rose
                Color.argb(0,   255, 255, 255)
            ),
            floatArrayOf(0f, 0.3f, 0.5f, 0.7f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawRoundRect(boundsF, cornerRadius, cornerRadius, shimmerPaint)
    }

    // -----------------------------------------------------------------------
    // Blur capture — PixelCopy (API 26+) of the actual screen behind this view
    // -----------------------------------------------------------------------

    /**
     * Schedule a fresh background capture. Debounced so rapid scroll events don't
     * queue hundreds of captures — only the last one in the debounce window fires.
     */
    fun invalidateBlur() {
        captureRunnable?.let { mainHandler.removeCallbacks(it) }
        val r = Runnable { performCapture() }
        captureRunnable = r
        mainHandler.postDelayed(r, captureDebounceMs)
    }

    private fun performCapture() {
        if (width == 0 || height == 0 || captureInProgress) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val window = (context as? Activity)?.window ?: return
            captureWithPixelCopy(window)
        }
        // Below API 26: no capture — layers 2–6 still render the glass aesthetic
    }

    private fun captureWithPixelCopy(window: android.view.Window) {
        val loc = IntArray(2)
        getLocationInWindow(loc)
        val rect = Rect(loc[0], loc[1], loc[0] + width, loc[1] + height)

        // Clamp to window bounds (glass may overlap status bar area)
        val decorView = window.decorView
        rect.left   = rect.left.coerceAtLeast(0)
        rect.top    = rect.top.coerceAtLeast(0)
        rect.right  = rect.right.coerceAtMost(decorView.width)
        rect.bottom = rect.bottom.coerceAtMost(decorView.height)
        if (rect.isEmpty) return

        val dest = Bitmap.createBitmap(rect.width(), rect.height(), Bitmap.Config.ARGB_8888)
        captureInProgress = true

        PixelCopy.request(window, rect, dest, { result ->
            captureInProgress = false
            if (result == PixelCopy.SUCCESS) {
                // Blur on background thread — it's CPU-bound
                Thread {
                    val blurred = multiPassBoxBlur(dest, blurRadius)
                    dest.recycle()
                    mainHandler.post {
                        val old = blurBitmap
                        blurBitmap = blurred
                        old?.recycle()
                        invalidate()
                    }
                }.start()
            } else {
                dest.recycle()
            }
        }, mainHandler)
    }

    // -----------------------------------------------------------------------
    // Multi-pass box blur  (3 passes ≈ Gaussian, O(w·h) per pass)
    // -----------------------------------------------------------------------

    /**
     * Approximates a Gaussian blur using 3 successive horizontal + vertical box blur
     * passes. Fast, allocation-light, and produces smooth, high-quality results.
     * @param radius  per-pass box half-width (total spread = radius * sqrt(3 * 2))
     */
    private fun multiPassBoxBlur(src: Bitmap, radius: Int): Bitmap {
        val w = src.width
        val h = src.height
        val pixels = IntArray(w * h)
        src.getPixels(pixels, 0, w, 0, 0, w, h)

        repeat(3) { // 3 passes approximates Gaussian
            boxBlurH(pixels, w, h, radius)
            boxBlurV(pixels, w, h, radius)
        }

        val out = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        out.setPixels(pixels, 0, w, 0, 0, w, h)
        return out
    }

    private fun boxBlurH(pixels: IntArray, w: Int, h: Int, r: Int) {
        val div = (r + r + 1).toFloat()
        for (y in 0 until h) {
            val base = y * w
            var rSum = 0; var gSum = 0; var bSum = 0
            for (dx in -r..r) {
                val px = pixels[base + dx.coerceIn(0, w - 1)]
                rSum += (px shr 16) and 0xFF
                gSum += (px shr 8) and 0xFF
                bSum +=  px and 0xFF
            }
            for (x in 0 until w) {
                pixels[base + x] = (0xFF shl 24) or
                    ((rSum / div).toInt() shl 16) or
                    ((gSum / div).toInt() shl 8) or
                    (bSum / div).toInt()
                val addPx = pixels[base + (x + r + 1).coerceIn(0, w - 1)]
                val remPx = pixels[base + (x - r).coerceIn(0, w - 1)]
                rSum += ((addPx shr 16) and 0xFF) - ((remPx shr 16) and 0xFF)
                gSum += ((addPx shr 8) and 0xFF) - ((remPx shr 8) and 0xFF)
                bSum +=  (addPx and 0xFF) - (remPx and 0xFF)
            }
        }
    }

    private fun boxBlurV(pixels: IntArray, w: Int, h: Int, r: Int) {
        val div = (r + r + 1).toFloat()
        for (x in 0 until w) {
            var rSum = 0; var gSum = 0; var bSum = 0
            for (dy in -r..r) {
                val px = pixels[dy.coerceIn(0, h - 1) * w + x]
                rSum += (px shr 16) and 0xFF
                gSum += (px shr 8) and 0xFF
                bSum +=  px and 0xFF
            }
            for (y in 0 until h) {
                pixels[y * w + x] = (0xFF shl 24) or
                    ((rSum / div).toInt() shl 16) or
                    ((gSum / div).toInt() shl 8) or
                    (bSum / div).toInt()
                val addPx = pixels[(y + r + 1).coerceIn(0, h - 1) * w + x]
                val remPx = pixels[(y - r).coerceIn(0, h - 1) * w + x]
                rSum += ((addPx shr 16) and 0xFF) - ((remPx shr 16) and 0xFF)
                gSum += ((addPx shr 8) and 0xFF) - ((remPx shr 8) and 0xFF)
                bSum +=  (addPx and 0xFF) - (remPx and 0xFF)
            }
        }
    }

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------
    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        shimmerAnimator.start()
        // First capture — small delay so the view is fully laid out and visible
        mainHandler.postDelayed({ invalidateBlur() }, 300)
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        shimmerAnimator.cancel()
        mainHandler.removeCallbacksAndMessages(null)
        blurBitmap?.recycle()
        blurBitmap = null
    }
}
