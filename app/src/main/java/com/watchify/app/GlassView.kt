package com.watchify.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.RenderEffect
import android.graphics.Shader
import android.os.Build
import android.view.View

class GlassView(context: Context) : View(context) {

    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            setRenderEffect(RenderEffect.createBlurEffect(40f, 40f, Shader.TileMode.CLAMP))
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        // On API 31+ the RenderEffect blur is applied automatically by the hardware renderer;
        // calling target.draw(canvas) here is redundant and unsafe on HW-accelerated views.
        // On older APIs we paint a solid dark overlay as a fallback.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            canvas.drawColor(Color.parseColor("#E61C1C1E"))
        }
    }
}
