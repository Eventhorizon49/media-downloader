package com.eventhorizon.mediadownloader

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 72, 48, 48)
            gravity = Gravity.CENTER_HORIZONTAL
            setBackgroundColor(Color.rgb(246, 247, 249))
        }
        val title = TextView(this).apply {
            text = "Media Downloader Private"
            textSize = 26f
            setTextColor(Color.rgb(21, 23, 26))
        }
        val info = TextView(this).apply {
            text = "Enable Copy Watcher once. After that, copying a supported Instagram, X/Twitter or Reddit link can show a Download popup. Clipboard text is not stored."
            textSize = 16f
            setTextColor(Color.DKGRAY)
            setPadding(0, 28, 0, 28)
        }
        val enable = Button(this).apply {
            text = "Enable Copy Watcher"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        }
        val openWeb = Button(this).apply {
            text = "Open Web Downloader"
            setOnClickListener {
                startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(BASE)))
            }
        }
        root.addView(title)
        root.addView(info)
        root.addView(enable)
        root.addView(openWeb)
        setContentView(root)

        if (intent?.action == Intent.ACTION_SEND) {
            val shared = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (!shared.isNullOrBlank()) Downloader.downloadBest(this, shared)
        }
    }

    companion object { const val BASE = "https://media-downloader-pcbv.onrender.com" }
}
