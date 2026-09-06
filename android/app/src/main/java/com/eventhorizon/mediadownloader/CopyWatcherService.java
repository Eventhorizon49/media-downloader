package com.eventhorizon.mediadownloader;

import android.accessibilityservice.AccessibilityService;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.view.Gravity;
import android.view.ViewGroup;
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

    private GradientDrawable bg(int color, float radiusDp, int strokeColor) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(radiusDp * getResources().getDisplayMetrics().density);
        if (strokeColor != Color.TRANSPARENT) d.setStroke((int)(1 * getResources().getDisplayMetrics().density), strokeColor);
        return d;
    }

    private void showPrompt(String url) {
        removePrompt();
        WindowManager wm = (WindowManager)getSystemService(WINDOW_SERVICE);
        float den = getResources().getDisplayMetrics().density;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding((int)(18*den),(int)(15*den),(int)(18*den),(int)(15*den));
        box.setBackground(bg(Color.rgb(13,18,32), 20, Color.rgb(45,58,88)));
        box.setElevation(22f);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText("Media Downloader");
        title.setTextSize(17);
        title.setTextColor(Color.WHITE);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        top.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView close = new TextView(this);
        close.setText("×");
        close.setTextSize(24);
        close.setGravity(Gravity.CENTER);
        close.setTextColor(Color.rgb(170,181,207));
        close.setPadding((int)(8*den),0,(int)(4*den),0);
        close.setOnClickListener(v -> removePrompt());
        top.addView(close, new LinearLayout.LayoutParams((int)(40*den),(int)(40*den)));

        TextView sub = new TextView(this);
        String h = Uri.parse(url).getHost();
        sub.setText((h == null ? "Supported link" : h) + "  ·  Best available quality");
        sub.setTextSize(12);
        sub.setTextColor(Color.rgb(145,158,190));
        sub.setPadding(0,(int)(3*den),0,(int)(12*den));

        Button download = new Button(this);
        download.setText("Download");
        download.setTextColor(Color.WHITE);
        download.setTextSize(15);
        download.setAllCaps(false);
        download.setTypeface(null, android.graphics.Typeface.BOLD);
        download.setBackground(bg(Color.rgb(39,110,255), 14, Color.TRANSPARENT));
        download.setOnClickListener(v -> {
            removePrompt();
            Downloader.downloadBest(this, url);
        });

        box.addView(top);
        box.addView(sub);
        box.addView(download, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,(int)(52*den)));

        WindowManager.LayoutParams p = new WindowManager.LayoutParams(
                (int)(330*den), WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        p.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        p.y = (int)(88*den);
        wm.addView(box, p);
        overlay = box;
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
