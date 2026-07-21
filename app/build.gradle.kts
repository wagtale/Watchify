import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application") version "8.2.2"
    id("org.jetbrains.kotlin.android") version "1.9.22"
}

val envFile = project.rootProject.file(".env")
val envProps = Properties()
if (envFile.exists()) {
    envProps.load(FileInputStream(envFile))
}

val keystoreFile = project.rootProject.file("keystore.properties")
val keystoreProps = Properties()
if (keystoreFile.exists()) {
    keystoreProps.load(FileInputStream(keystoreFile))
}

android {
    namespace = "com.watchify.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.watchify.app"
        minSdk = 26
        targetSdk = 34
        
        val versionFile = project.rootProject.file("version.properties")
        val versionProps = Properties()
        if (versionFile.exists()) {
            versionProps.load(FileInputStream(versionFile))
        }
        val major = versionProps.getProperty("MAJOR", "1").toInt()
        val minor = versionProps.getProperty("MINOR", "0").toInt()
        val patch = versionProps.getProperty("PATCH", "0").toInt()
        val code = versionProps.getProperty("CODE", "1").toInt()
        
        versionCode = code
        versionName = "$major.$minor.$patch"
        
        buildConfigField("String", "WINDY_API_KEY", "\"${envProps.getProperty("WINDY_API_KEY", "")}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    signingConfigs {
        create("release") {
            storeFile = file(keystoreProps.getProperty("storeFile", "release.jks"))
            storePassword = keystoreProps.getProperty("storePassword", "")
            keyAlias = keystoreProps.getProperty("keyAlias", "")
            keyPassword = keystoreProps.getProperty("keyPassword", "")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            isMinifyEnabled = false
        }
    }
    
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    
    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("androidx.health.connect:connect-client:1.1.0-alpha07")
}
