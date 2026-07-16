# Watchify Full Security Audit & Remediation Report

Here is a comprehensive breakdown of the security posture of the application following our recent sweeps and updates.

### 1. Cryptography & Key Management
*   **Status: ✅ SECURE**
*   **What we found:** The `build.gradle.kts` file contained a hardcoded signing keystore password (`watchify123`) committed to the public Git repository. 
*   **What we did:** 
    *   Wiped the compromised `release.jks` file completely.
    *   Re-rolled the keystore using a cryptographically secure 64-character random password.
    *   Abstracted the `storePassword` and `keyPassword` out of `build.gradle.kts` and into a local `keystore.properties` file.
    *   Added `keystore.properties` to `.gitignore` to prevent future leaks.
    *   *Note: This matches the secure `.env` pattern already successfully implemented for the `WINDY_API_KEY`.*

### 2. Network Traffic & API Encryption
*   **Status: ✅ SECURE**
*   **What we found:** The fallback geolocator (used when GPS is unavailable) was calling `http://ip-api.com/json/`. This is an unencrypted cleartext HTTP endpoint, meaning location data could be intercepted by a man-in-the-middle (MITM) on public Wi-Fi. (Android 9+ blocks this by default anyway).
*   **What we did:** Migrated both `WeatherManager.kt` and `MainActivity.kt` to use `https://ipapi.co/json/`. All outbound network requests are now encrypted over TLS/HTTPS. The `AndroidManifest.xml` does **not** declare `android:usesCleartextTraffic="true"`, meaning Android will strictly enforce HTTPS everywhere.

### 3. Application Data Storage & Databases
*   **Status: ✅ SECURE**
*   **What we found:** The `SQLiteOpenHelper` database (`HealthDatabaseHelper`) stores highly sensitive biometric data (heart rate, SpO2, sleep, menstrual cycles). Previously, `AndroidManifest.xml` had `android:allowBackup="true"`, allowing anyone with physical access to the phone to extract the database via ADB.
*   **What we did:** 
    *   Flipped `allowBackup="false"` in the Manifest. The database is now strictly confined to the application's secure sandbox and cannot be backed up or extracted via ADB on non-rooted devices.
    *   Verified that `HealthDataProcessor.kt` exclusively uses parameterized `rawQuery` strings (e.g., `?`) rather than string concatenation, neutralizing any potential SQL injection vulnerabilities.

### 4. Logging & Diagnostics
*   **Status: ✅ SECURE**
*   **What we found:** `NotificationMonitor.kt` was aggressively logging the full plaintext titles and bodies of intercepted notifications (including SMS 2FA codes and banking alerts) to the system Logcat.
*   **What we did:** Wrapped the `Log.d` call in an `if (BuildConfig.DEBUG)` check. Production/Release APKs will completely compile this line out, ensuring sensitive user data never touches the persistent system log buffer.

### 5. Inter-Process Communication (IPC) & Components
*   **Status: ✅ SECURE**
*   **What we found:** We reviewed the Android Manifest for potentially dangerous `exported="true"` flags on Services or Activities.
*   **What we did:** Verified that the only exported components are:
    *   `MainActivity`: Required for the launcher.
    *   `NotificationMonitor`: Exported, but securely locked behind `android.permission.BIND_NOTIFICATION_LISTENER_SERVICE` (meaning only the Android OS can bind to it, not malicious third-party apps).
    *   `BootReceiver`: Exported, but safely validates `Intent.ACTION_BOOT_COMPLETED` internally.
    *   `DebugActivity` and `WatchDriverService` are explicitly marked `exported="false"`.

### 6. Over-The-Air BLE Protocol
*   **Status: 🚧 VENDOR LIMITATION**
*   **What we found:** The physical watch hardware/firmware does not support application-layer encryption (no AES/RSA opcodes). Payloads like notification text are sent over BLE in plaintext.
*   **What we did:** Added a clear disclaimer to the `README.md` `Security & Limitations` section. We instruct users that they **must** manually "Pair" (Bond) the watch in their Android system settings to force the Android Bluetooth stack to encrypt the link-layer via AES-CCM.
