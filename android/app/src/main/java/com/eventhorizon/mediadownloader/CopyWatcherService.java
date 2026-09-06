package com.eventhorizon.mediadownloader;

import android.accessibilityservice.AccessibilityService;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.net.Uri;
import android.view.Gravity;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class CopyWatcherService extends AccessibilityService {
    private ClipboardManager clipboard;
    private String lastValue;
    private LinearLayout overlay;
    private final ClipboardManager.OnPrimaryClipChangedListener listener = this::checkClipboard;

    @Override protected void onServiceConnected() {
        clipboard = (ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.addPrimaryClipChangedListener(listener);
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) { checkClipboard(); }
    @Override public void onInterrupt() {}

    private boolean supported(String text) {
        String s = text.toLowerCase();
        return s.contains("instagram.com/") || s.contains("x.com/") || s.contains("twitter.com/") || s.contains("reddit.com/") || s.contains("redd.it/");
    }

    private void checkClipboard() {
        try {
            ClipData clip = clipboard.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) return;
            CharSequence cs = clip.getItemAt(0).coerceToText(this);
            if (cs == null) return;
            String text = cs.toString().trim();
            if (text.equals(lastValue) || !supported(text)) return;
            lastValue = text;
            showPrompt(text);
        } catch (Exception ignored) {}
    }

    private void showPrompt(String url) {
        removePrompt();
        WindowManager wm = (WindowManager)getSystemService(WINDOW_SERVICE);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL); box.setPadding(32,28,32,28); box.setBackgroundColor(Color.WHITE); box.setElevation(18f);
        TextView title = new TextView(this); title.setText("Download copied media?"); title.setTextSize(18); title.setTextColor(Color.BLACK);
        TextView host = new TextView(this); String h = Uri.parse(url).getHost(); host.setText(h == null ? url : h); host.setTextSize(13); host.setTextColor(Color.DKGRAY); host.setPadding(0,10,0,14);
        Button download = new Button(this); download.setText("Download best quality");
        download.setOnClickListener(v -> { removePrompt(); Downloader.downloadBest(this, url); });
        Button dismiss = new Button(this); dismiss.setText("Dismiss"); dismiss.setOnClickListener(v -> removePrompt());
        box.addView(title); box.addView(host); box.addView(download); box.addView(dismiss);
        WindowManager.LayoutParams p = new WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN, PixelFormat.TRANSLUCENT);
        p.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL; p.y = 110;
        wm.addView(box, p); overlay = box;
    }

    private void removePrompt() {
        if (overlay == null) return;
        try { ((WindowManager)getSystemService(WINDOW_SERVICE)).removeView(overlay); } catch (Exception ignored) {}
        overlay = null;
    }

    @Override public void onDestroy() {
        removePrompt();
        if (clipboard != null) clipboard.removePrimaryClipChangedListener(listener);
        super.onDestroy();
    }
}
