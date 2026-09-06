plugins {
    id("com.android.application")
}

android {
    namespace = "com.eventhorizon.mediadownloader"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.eventhorizon.mediadownloader.finalapp"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "2.0"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core:1.15.0")
}
