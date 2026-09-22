plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "se.svampradar.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "se.svampradar.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "1.2.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
        manifestPlaceholders["app_name_flavor"] = "Svampstället"
    }

    flavorDimensions += "region"
    productFlavors {
        create("full") {
            dimension = "region"
            versionNameSuffix = "-full"
            manifestPlaceholders["app_name_flavor"] = "Svampstället"
            buildConfigField("Double", "INITIAL_LAT", "58.00")
            buildConfigField("Double", "INITIAL_LON", "12.30")
            buildConfigField("Double", "INITIAL_ZOOM", "9.0")
        }
        create("aleLillaEdet") {
            dimension = "region"
            versionNameSuffix = "-ale"
            manifestPlaceholders["app_name_flavor"] = "Svampstället (Ale & Lilla Edet)"
            buildConfigField("Double", "INITIAL_LAT", "58.00")
            buildConfigField("Double", "INITIAL_LON", "12.18")
            buildConfigField("Double", "INITIAL_ZOOM", "10.5")
        }
        create("goteborg") {
            dimension = "region"
            versionNameSuffix = "-goteborg"
            manifestPlaceholders["app_name_flavor"] = "Svampstället (Göteborg)"
            buildConfigField("Double", "INITIAL_LAT", "57.70")
            buildConfigField("Double", "INITIAL_LON", "11.97")
            buildConfigField("Double", "INITIAL_ZOOM", "11.0")
        }
        create("lidkoping") {
            dimension = "region"
            versionNameSuffix = "-lidkoping"
            manifestPlaceholders["app_name_flavor"] = "Svampstället (Lidköping)"
            buildConfigField("Double", "INITIAL_LAT", "58.50")
            buildConfigField("Double", "INITIAL_LON", "13.16")
            buildConfigField("Double", "INITIAL_ZOOM", "11.0")
        }
        create("mark") {
            dimension = "region"
            versionNameSuffix = "-mark"
            manifestPlaceholders["app_name_flavor"] = "Svampstället (Mark)"
            buildConfigField("Double", "INITIAL_LAT", "57.48")
            buildConfigField("Double", "INITIAL_LON", "12.66")
            buildConfigField("Double", "INITIAL_ZOOM", "10.5")
        }
    }

    signingConfigs {
        create("release") {
            storeFile = file("svampradar-release.keystore")
            storePassword = "svampradar123"
            keyAlias = "svampradar"
            keyPassword = "svampradar123"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            ndk {
                abiFilters.add("arm64-v8a")
            }
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation("androidx.compose.material:material-icons-extended")
    implementation(libs.androidx.navigation.compose)
    
    // MapLibre
    implementation(libs.maplibre.android.sdk)
    
    // Additional features
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.core.splashscreen)

    testImplementation(libs.junit)
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
    testImplementation("org.robolectric:robolectric:4.13")
    testImplementation("androidx.test:core:1.6.1")
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
