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

android {
    namespace = "com.watchify.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.watchify.app"
        minSdk = 26
        targetSdk = 34
        
        fun getGitCommitCount(): Int {
            return try {
                val process = ProcessBuilder("git", "rev-list", "--count", "HEAD").redirectErrorStream(true).start()
                val count = process.inputStream.bufferedReader().readText().trim().toInt()
                
                val diffProcess = ProcessBuilder("git", "status", "--porcelain").redirectErrorStream(true).start()
                val hasChanges = diffProcess.inputStream.bufferedReader().readText().trim().isNotEmpty()
                
                if (hasChanges) count + 1 else count
            } catch (e: Exception) {
                1
            }
        }
        val commitCount = getGitCommitCount()
        
        versionCode = commitCount
        versionName = "1.0.$commitCount"
        
        buildConfigField("String", "WINDY_API_KEY", "\"${envProps.getProperty("WINDY_API_KEY", "")}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    signingConfigs {
        create("release") {
            storeFile = file("release.jks")
            storePassword = "watchify123"
            keyAlias = "watchify"
            keyPassword = "watchify123"
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
}
