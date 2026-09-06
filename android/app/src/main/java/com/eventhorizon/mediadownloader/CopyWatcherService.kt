package com.eventhorizon.mediadownloader

import android.accessibilityservice.AccessibilityService
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.view.Gravity
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class CopyWatcherService : AccessibilityService() {
    private lateinit var clipboard: ClipboardManager
    private var lastValue: String? = null
    private var overlay: LinearLayout? = null

    override fun onServiceConnected() {
        clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.addPrimaryClipChangedListener { checkClipboard() }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        checkClipboard()
    }

    override fun onInterrupt() = Unit

    private fun checkClipboard() {
        val clip: ClipData = clipboard.primaryClip ?: return
        if (clip.itemCount == 0) return
        val text = clip.getItemAt(0).coerceToText(this)?.toString()?.trim() ?: return
        if (text == lastValue || !isSupported(text)) return
        lastValue = text
        showPrompt(text)
    }

    private fun isSupported(text: String): Boolean {
        val s = text.lowercase()
        return s.contains("instagram.com/") || s.contains("x.com/") || s.contains("twitter.com/") || s.contains("reddit.com/") || s.contains("redd.it/")
    }

    private fun showPrompt(url: String) {
        removePrompt()
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 28, 32, 28)
            setBackgroundColor(Color.WHITE)
            elevation = 18f
        }
        val title = TextView(this).apply {
            text = "Download copied media?"
            textSize = 18f
            setTextColor(Color.BLACK)
        }
        val host = TextView(this).apply {
            text = runCatching { android.net.Uri.parse(url).host ?: url }.getOrDefault(url)
            textSize = 13f
            setTextColor(Color.DKGRAY)
            setPadding(0, 10, 0, 14)
        }
        val download = Button(this).apply {
            text = "Download best quality"
            setOnClickListener {
                removePrompt()
                Downloader.downloadBest(this@CopyWatcherService, url)
            }
        }
        val dismiss = Button(this).apply {
            text = "Dismiss"
            setOnClickListener { removePrompt() }
        }
        box.addView(title)
        box.addView(host)
        box.addView(download)
        box.addView(dismiss)

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = 110
        }
        wm.addView(box, params)
        overlay = box
    }

    private fun removePrompt() {
        val view = overlay ?: return
        runCatching { (getSystemService(WINDOW_SERVICE) as WindowManager).removeView(view) }
        overlay = null
    }

    override fun onDestroy() {
        removePrompt()
        if (::clipboard.isInitialized) clipboard.removePrimaryClipChangedListener { checkClipboard() }
        super.onDestroy()
    }
}
