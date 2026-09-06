package com.eventhorizon.mediadownloader

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object Downloader {
    private fun supported(text: String): Boolean {
        val s = text.lowercase()
        return s.contains("instagram.com/") || s.contains("x.com/") || s.contains("twitter.com/") || s.contains("reddit.com/") || s.contains("redd.it/")
    }

    fun downloadBest(context: Context, raw: String) {
        val mediaUrl = Regex("https?://\\S+").find(raw)?.value?.trimEnd('.', ',', ')', ']', '}') ?: raw.trim()
        if (!supported(mediaUrl)) {
            Toast.makeText(context, "Not a supported media link", Toast.LENGTH_SHORT).show()
            return
        }
        Toast.makeText(context, "Preparing download…", Toast.LENGTH_SHORT).show()
        Thread {
            try {
                val conn = URL(MainActivity.BASE + "/api/analyze").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.connectTimeout = 30000
                conn.readTimeout = 90000
                conn.doOutput = true
                val body = JSONObject().put("url", mediaUrl).toString().toByteArray()
                conn.outputStream.use { it.write(body) }
                val code = conn.responseCode
                val response = (if (code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
                if (code !in 200..299) throw IllegalStateException(JSONObject(response).optString("detail", "Could not analyze link"))
                val token = JSONObject(response).getString("token")
                val downloadUrl = MainActivity.BASE + "/api/download?mode=best&token=" + Uri.encode(token)
                val request = DownloadManager.Request(Uri.parse(downloadUrl))
                    .setTitle("Media Downloader")
                    .setDescription("Downloading best available quality")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setAllowedOverMetered(true)
                    .setAllowedOverRoaming(true)
                val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(context, "Download started", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(context, e.message ?: "Download failed", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }
}
