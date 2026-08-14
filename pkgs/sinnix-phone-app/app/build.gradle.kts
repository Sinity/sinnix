plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "dev.sinnix.phone"
    // 36 because androidx.health.connect 1.1.0 refuses to be depended on by
    // anything compiled against less. Unrelated to targetSdk, which is a
    // behaviour opt-in and stays at 33 for the BOOT_COMPLETED reason below.
    compileSdk = 36

    // Pinned to what pkg.nix installs. Left unset, AGP picks its own default
    // and the build fails inside the sandbox with a missing-component error
    // that reads like a network problem instead of a version mismatch.
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "dev.sinnix.phone"
        minSdk = 29

        // Pinned, not stale. API 34 forbids starting a microphone foreground
        // service from a BOOT_COMPLETED receiver (FOREGROUND_SERVICE_START_NOT_ALLOWED
        // with the while-in-use restriction), and resuming capture after a
        // reboot without the operator touching anything is a standing
        // acceptance criterion. Raising this needs a Direct Boot design first.
        targetSdk = 33

        versionCode = 2
        versionName = "0.2.0"

        // One ABI, because there is one device. onnxruntime ships native
        // libraries for four architectures and three of them are for phones
        // this app will never be installed on -- carrying them cost 64 MB of a
        // 104 MB APK, on a sideloaded build that is copied over adb.
        ndk { abiFilters += "arm64-v8a" }
    }

    buildTypes {
        release {
            // R8 is deliberately off. The APK ships unsigned and is signed at
            // install time against a host-local keystore; shrinking buys a few
            // hundred KB on a sideloaded app and costs a whole class of
            // reflection/serializer surprises that would only ever appear on
            // the one device that matters.
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "/META-INF/DEPENDENCIES",
            "DebugProbesKt.bin",
        )
    }

    // No signingConfig on release, deliberately: AGP then emits
    // app-release-unsigned.apk, which is exactly the artifact this build wants.
    // sinnix-phone-app-install owns the keystore so `adb install -r` stays an
    // upgrade and the app's runtime grants survive.
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.glance.appwidget)
    implementation(libs.androidx.glance.material3)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.okhttp)
    // Silero VAD, so the phone gates speech with the same engine the desktop
    // does rather than an energy threshold that would stream every passing car.
    implementation(libs.onnxruntime.android)
    // Read the band's data directly; the scheduled export never lands.
    implementation(libs.androidx.health.connect)
}
