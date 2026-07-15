package com.watchify.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.RenderEffect
import android.graphics.Shader
import android.os.Build
import android.view.View

class GlassView(context: Context) : View(context) {

    var targetView: View? = null
        set(value) {
            field = value
            invalidate()
        }

    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            setRenderEffect(RenderEffect.createBlurEffect(40f, 40f, Shader.TileMode.CLAMP))
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val target = targetView
        if (target != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val saveCount = canvas.save()
            val location = IntArray(2)
            getLocationInWindow(location)
            val targetLocation = IntArray(2)
            target.getLocationInWindow(targetLocation)
            canvas.translate((targetLocation[0] - location[0]).toFloat(), (targetLocation[1] - location[1]).toFloat())
            target.draw(canvas)
            canvas.restoreToCount(saveCount)
        } else {
            // Fallback for older Android versions
            canvas.drawColor(Color.parseColor("#E61C1C1E"))
        }
    }
}
