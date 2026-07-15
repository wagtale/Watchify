package com.watchify.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class WatchAccessibilityService : AccessibilityService() {

    companion object {
        var instance: WatchAccessibilityService? = null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Not used
    }

    override fun onInterrupt() {
        // Not used
    }

    override fun onUnbind(intent: Intent?): Boolean {
        instance = null
        return super.onUnbind(intent)
    }

    fun clickShutter() {
        val root = rootInActiveWindow ?: return
        
        // Strategy 1: Find by view ID or content description
        if (findAndClickShutterNode(root)) {
            return
        }

        // Strategy 2: If we couldn't find the node specifically, we tap the bottom center of the screen (Portrait)
        // or right center (Landscape) assuming it's the default camera layout
        val metrics = resources.displayMetrics
        val width = metrics.widthPixels
        val height = metrics.heightPixels

        val path = Path()
        if (height > width) {
            // Portrait: Bottom center (around 15% from bottom)
            path.moveTo(width / 2f, height * 0.85f)
        } else {
            // Landscape: Right center
            path.moveTo(width * 0.85f, height / 2f)
        }

        val stroke = GestureDescription.StrokeDescription(path, 0, 100)
        val builder = GestureDescription.Builder()
        builder.addStroke(stroke)
        dispatchGesture(builder.build(), null, null)
    }

    private fun findAndClickShutterNode(node: AccessibilityNodeInfo): Boolean {
        val queue = java.util.LinkedList<AccessibilityNodeInfo>()
        queue.add(node)

        while (queue.isNotEmpty()) {
            val current = queue.removeFirst()
            val desc = current.contentDescription?.toString()?.lowercase() ?: ""
            val viewId = current.viewIdResourceName?.lowercase() ?: ""

            if (current.isClickable && (desc.contains("shutter") || desc.contains("photo") || desc.contains("take picture") || desc.contains("record") || viewId.contains("shutter"))) {
                current.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                return true
            }

            for (i in 0 until current.childCount) {
                current.getChild(i)?.let { queue.add(it) }
            }
        }
        return false
    }
}
