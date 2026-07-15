# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.kts.

# Coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# Bleak/Bluetooth related classes if using reflection (just in case)
-keep class com.watchify.app.WatchProtocol { *; }

# Keep data models used for JSON serialization or hardware structs
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# Android UI
-keep class com.watchify.app.MainActivity { *; }
-keepclassmembers class com.watchify.app.MainActivity {
    public void *(android.view.View);
}
