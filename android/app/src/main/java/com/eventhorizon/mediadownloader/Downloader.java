package com.eventhorizon.mediadownloader;

import android.app.DownloadManager;
import android.content.Context;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Downloader {
    private Downloader() {}

    private static boolean supported(String text) {
        String s = text.toLowerCase();
        return s.contains("instagram.com/") || s.contains("x.com/") || s.contains("twitter.com/") || s.contains("reddit.com/") || s.contains("redd.it/");
    }

    private static String firstUrl(String raw) {
        Matcher m = Pattern.compile("https?://\\S+").matcher(raw);
        String u = m.find() ? m.group() : raw.trim();
        while (!u.isEmpty() && ".,)]}".indexOf(u.charAt(u.length() - 1)) >= 0) {
            u = u.substring(0, u.length() - 1);
        }
        return u;
    }

    public static void downloadBest(Context context, String raw) {
        String mediaUrl = firstUrl(raw);
        if (!supported(mediaUrl)) {
            Toast.makeText(context, "Unsupported link", Toast.LENGTH_SHORT).show();
            return;
        }

        Toast.makeText(context, "Preparing best quality…", Toast.LENGTH_SHORT).show();

        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(MainActivity.BASE + "/api/analyze").openConnection();
                c.setRequestMethod("POST");
                c.setRequestProperty("Content-Type", "application/json");
                c.setConnectTimeout(30000);
                c.setReadTimeout(90000);
                c.setDoOutput(true);

                byte[] body = new JSONObject().put("url", mediaUrl).toString().getBytes(StandardCharsets.UTF_8);
                c.getOutputStream().write(body);

                int code = c.getResponseCode();
                InputStream in = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
                BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = r.readLine()) != null) sb.append(line);

                JSONObject response = new JSONObject(sb.toString());
                if (code < 200 || code >= 300) {
                    throw new IllegalStateException(response.optString("detail", "Could not analyze link"));
                }

                JSONArray items = response.optJSONArray("items");
                if (items == null || items.length() == 0) {
                    throw new IllegalStateException("No downloadable media found");
                }

                DownloadManager dm = (DownloadManager) context.getSystemService(Context.DOWNLOAD_SERVICE);
                int started = 0;
                for (int i = 0; i < items.length(); i++) {
                    JSONObject item = items.optJSONObject(i);
                    if (item == null) continue;
                    String token = item.optString("token", "");
                    if (token.isEmpty()) continue;

                    Uri uri = Uri.parse(MainActivity.BASE + "/api/download?mode=best&token=" + Uri.encode(token));
                    DownloadManager.Request req = new DownloadManager.Request(uri)
                            .setTitle(items.length() > 1 ? "Media Downloader · " + (i + 1) + "/" + items.length() : "Media Downloader")
                            .setDescription("Best available quality")
                            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                            .setAllowedOverMetered(true)
                            .setAllowedOverRoaming(true);
                    dm.enqueue(req);
                    started++;
                }

                if (started == 0) throw new IllegalStateException("No downloadable media found");
                final int count = started;
                new Handler(Looper.getMainLooper()).post(() ->
                        Toast.makeText(context, count == 1 ? "Download started" : count + " downloads started", Toast.LENGTH_SHORT).show());

            } catch (Exception e) {
                String message = e.getMessage() == null ? "Download failed" : e.getMessage();
                new Handler(Looper.getMainLooper()).post(() -> Toast.makeText(context, message, Toast.LENGTH_LONG).show());
            }
        }).start();
    }
}
