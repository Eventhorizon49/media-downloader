package com.eventhorizon.mediadownloader;

import android.app.*;
import android.content.*;
import android.os.*;
import androidx.core.app.NotificationCompat;

public class DownloadService extends IntentService {
    private static final String CH="media_downloads";
    public DownloadService(){ super("MediaDownloader"); }

    public static void start(Context c,String url){
        Intent i=new Intent(c,DownloadService.class).putExtra("url",url);
        if(Build.VERSION.SDK_INT>=26)c.startForegroundService(i); else c.startService(i);
    }

    @Override public void onCreate(){
        super.onCreate();
        NotificationManager nm=getSystemService(NotificationManager.class);
        if(Build.VERSION.SDK_INT>=26)nm.createNotificationChannel(new NotificationChannel(CH,"Media downloads",NotificationManager.IMPORTANCE_LOW));
        startForeground(41,new NotificationCompat.Builder(this,CH).setSmallIcon(android.R.drawable.stat_sys_download).setContentTitle("Media Downloader").setContentText("Preparing download…").setOngoing(true).build());
    }

    @Override protected void onHandleIntent(Intent intent){
        String url=intent.getStringExtra("url");
        if(url!=null) Downloader.downloadBest(getApplicationContext(),url);
        try{Thread.sleep(1500);}catch(Exception ignored){}
        stopForeground(true);
        stopSelf();
    }
}
