package com.watchify.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Shader
import android.view.View

class GraphView(context: Context) : View(context) {

    private val multiDataPoints = mutableListOf<List<Float>>()
    private val colors = listOf("#34C759", "#007AFF", "#FF9500", "#FF3B30", "#AF52DE")
    
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#33FFFFFF")
        strokeWidth = 2f
        style = Paint.Style.STROKE
        pathEffect = android.graphics.DashPathEffect(floatArrayOf(10f, 10f), 0f)
    }

    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#8E8E93")
        textSize = 24f
        textAlign = Paint.Align.RIGHT
        typeface = androidx.core.content.res.ResourcesCompat.getFont(context, R.font.sf_pro_bold)
    }

    fun setData(points: List<Float>) {
        setMultiData(listOf(points))
    }

    fun setMultiData(multiPoints: List<List<Float>>) {
        multiDataPoints.clear()
        multiDataPoints.addAll(multiPoints)
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        
        if (multiDataPoints.isEmpty() || multiDataPoints.all { it.isEmpty() }) return
        
        val width = width.toFloat()
        val height = height.toFloat()
        val padding = 48f
        
        var globalMin = Float.MAX_VALUE
        var globalMax = Float.MIN_VALUE
        for (points in multiDataPoints) {
            val minP = points.minOrNull() ?: 0f
            val maxP = points.maxOrNull() ?: 100f
            if (minP < globalMin) globalMin = minP
            if (maxP > globalMax) globalMax = maxP
        }
        
        // Add a small margin to max and min
        val paddingVal = (globalMax - globalMin) * 0.1f
        globalMin -= paddingVal
        globalMax += paddingVal
        
        val range = if (globalMax == globalMin) 1f else (globalMax - globalMin)
        
        // Draw grid and max/min text
        val steps = 4
        for (i in 0..steps) {
            val y = padding + i * (height - 2 * padding) / steps
            canvas.drawLine(padding + 60, y, width - padding, y, gridPaint)
            
            // Draw scale values (invert i because 0 is top)
            val scaleVal = globalMax - (i * range / steps)
            canvas.drawText("${scaleVal.toInt()}", padding + 40, y + 8f, textPaint)
        }
        
        val graphStartX = padding + 60
        val graphWidth = width - padding - graphStartX
        
        multiDataPoints.forEachIndexed { seriesIndex, points ->
            if (points.isEmpty()) return@forEachIndexed
            val stepX = graphWidth / (points.size - 1).coerceAtLeast(1)
            val path = Path()
            val fillPath = Path()
            
            for (i in points.indices) {
                val x = graphStartX + i * stepX
                val y = height - padding - ((points[i] - globalMin) / range) * (height - 2 * padding)
                
                if (i == 0) {
                    path.moveTo(x, y)
                    fillPath.moveTo(x, height - padding)
                    fillPath.lineTo(x, y)
                } else {
                    path.lineTo(x, y)
                    fillPath.lineTo(x, y)
                }
                
                if (i == points.size - 1) {
                    fillPath.lineTo(x, height - padding)
                }
            }
            fillPath.close()
            
            val baseColorStr = colors[seriesIndex % colors.size]
            val baseColor = Color.parseColor(baseColorStr)
            
            val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = baseColor
                strokeWidth = 6f
                style = Paint.Style.STROKE
                strokeCap = Paint.Cap.ROUND
                strokeJoin = Paint.Join.ROUND
            }
            
            val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                style = Paint.Style.FILL
                shader = LinearGradient(
                    0f, padding, 0f, height - padding,
                    Color.argb(128, Color.red(baseColor), Color.green(baseColor), Color.blue(baseColor)),
                    Color.argb(0, Color.red(baseColor), Color.green(baseColor), Color.blue(baseColor)),
                    Shader.TileMode.CLAMP
                )
            }
            
            canvas.drawPath(fillPath, fillPaint)
            canvas.drawPath(path, linePaint)
        }
    }
}
