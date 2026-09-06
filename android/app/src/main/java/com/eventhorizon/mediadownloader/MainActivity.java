package com.eventhorizon.mediadownloader;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    public static final String BASE = "https://media-downloader-pcbv.onrender.com";
    private WebView web;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (handleShare(getIntent())) return;
        openWeb();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (!handleShare(intent) && web == null) openWeb();
    }

    private boolean handleShare(Intent intent) {
        if (Intent.ACTION_SEND.equals(intent.getAction()) && intent.getType() != null && intent.getType().startsWith("text/")) {
            String shared = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (shared != null && !shared.trim().isEmpty()) {
                DownloadService.start(this, shared);
                finish();
                return true;
            }
        }
        return false;
    }

    private void openWeb() {
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setLoadsImagesAutomatically(true);
        web.setWebViewClient(new WebViewClient());
        setContentView(web);
        web.loadUrl(BASE);
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
