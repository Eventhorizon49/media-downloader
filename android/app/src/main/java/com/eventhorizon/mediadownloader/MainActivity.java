package com.eventhorizon.mediadownloader;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

public class MainActivity extends Activity {
    public static final String BASE = "https://media-downloader-pcbv.onrender.com";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        handle(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handle(intent);
    }

    private void handle(Intent intent) {
        if (Intent.ACTION_SEND.equals(intent.getAction()) && "text/plain".equals(intent.getType())) {
            String shared = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (shared != null && !shared.trim().isEmpty()) {
                Downloader.downloadBest(getApplicationContext(), shared);
                finish();
                return;
            }
        }
        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(BASE)));
        finish();
    }
}
