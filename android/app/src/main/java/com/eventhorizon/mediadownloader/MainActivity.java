package com.eventhorizon.mediadownloader;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    public static final String BASE = "https://media-downloader-pcbv.onrender.com";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(48, 72, 48, 48);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setBackgroundColor(Color.rgb(246,247,249));

        TextView title = new TextView(this);
        title.setText("Media Downloader Private");
        title.setTextSize(26);
        title.setTextColor(Color.rgb(21,23,26));

        TextView info = new TextView(this);
        info.setText("Enable Copy Watcher once. Then copying a supported Instagram, X/Twitter or Reddit link can show a Download popup. Clipboard text is not stored.");
        info.setTextSize(16);
        info.setTextColor(Color.DKGRAY);
        info.setPadding(0,28,0,28);

        Button enable = new Button(this);
        enable.setText("Enable Copy Watcher");
        enable.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));

        Button web = new Button(this);
        web.setText("Open Web Downloader");
        web.setOnClickListener(v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(BASE))));

        root.addView(title); root.addView(info); root.addView(enable); root.addView(web);
        setContentView(root);

        Intent i = getIntent();
        if (Intent.ACTION_SEND.equals(i.getAction())) {
            String shared = i.getStringExtra(Intent.EXTRA_TEXT);
            if (shared != null && !shared.trim().isEmpty()) Downloader.downloadBest(this, shared);
        }
    }
}
