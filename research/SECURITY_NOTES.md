# Security Notes & Findings

Reverse engineering findings from `com.wtwd.utra` — notable from a security/privacy research perspective.

---

## 🔴 Critical: Hardcoded API Keys

All of the following credentials were found **in plaintext** in the compiled APK:

### 1. AI API Key
```
Key:   rh4s78cdvcw212a76
Field: Constant.AI_KEY
File:  com/wtwd/utra/constant/Constant.java
Use:   Authentication for AI chat backend (Baidu ERNIE / OpenAI GPT relay)
```

### 2. Google Maps API Key
```
Key:   AIzaSyDFkGsF5bmlYTEA-oFeatd4MOzZnE7yz8w
Field: Constant.GOOGLE_MAP_KEY
File:  com/wtwd/utra/constant/Constant.java
Use:   Google Maps SDK (sport route display, GPS tracking)
Risk:  Can be used to make Google Maps API calls billed to app owner
```

### 3. Weather Service API Key
```
Key:   uqV3vCNsUuPgL7cNZ71AtNcFGVvRXViJ
Field: Constant.WEATHER_KEY
File:  com/wtwd/utra/constant/Constant.java
Use:   Weather data API (likely Caiyun/Qweather or similar Chinese provider)
```

### 4. Huawei Maps Key
```
Key:   DAEDAPlpeYvgTWACx3YzdGFhBmKXS3CPUat3BnGvxIKZAlB3B5u6RdnuDwd6YUeK8YZh7uVS9MYoHIWT89lx+XARE7uNa/zsKVyUEA==
Field: Constant.HUAWEI_MAP_KEY
File:  com/wtwd/utra/constant/Constant.java
Use:   Huawei Map SDK
```

---

## 🔴 Critical: Plaintext Password Storage

```java
// SharedPrefsKey.PREF_KEY_PASSWORD = "PREF_KEY_PASSWORD"
// Stored in Android SharedPreferences (XML file) without any encryption
// File location: /data/data/com.wtwd.utra/shared_prefs/
```

**Impact**: Any app with `READ_EXTERNAL_STORAGE` or shell/root access on the device can read the stored password. No token-only auth flow — the raw password is persisted.

---

## 🟠 High: Backend URL Exposed

```
https://wr.watchhealth.com.cn/app-halfwit/
```

- Subdomain `app-halfwit` is an unusual name, possibly a development endpoint or internal codename.
- Full API endpoint paths can be recovered from `BaseApi.java` and related Retrofit interfaces.
- No certificate pinning observed in the decompiled code.

---

## 🟠 High: Phone Call Interception

The app registers a `BroadcastReceiver` and `TelephonyManager.PhoneStateListener` with `Integer.MAX_VALUE` priority:

```java
intentFilter.setPriority(Integer.MAX_VALUE);
intentFilter.addAction("android.intent.action.PHONE_STATE");
```

- This gives the app highest possible priority for receiving phone state broadcasts.
- The app reads **incoming caller number** from the broadcast.
- The app looks up the caller in **contacts** (`READ_CONTACTS` permission).
- Caller ID + contact name are forwarded over BLE to the watch.
- **Data retention**: The `MessageNotice` entity tracks which notification categories are enabled — the app only forwarding calls when `MessageNotice.a() != 0`, but the receiver is always registered.

---

## 🟠 High: Notification Listener Service (Always-On)

`NewsNotificationListenerService` is a `NotificationListenerService`:
- Has access to **all notifications** from all apps on the device.
- Reads notification title and content text for forwarding to watch.
- Maintains media session listening via `MediaSessionManager`.
- Gets song metadata (title, artist, album) from all media sessions.

This is expected behavior for a smartwatch companion, but the scope of data access is broad.

---

## 🟡 Medium: No Encryption on BLE Data

The BLE protocol uses a custom framing format (see `BLE_PROTOCOL.md`) with a CRC16 checksum, but **no encryption** is applied to the data in transit:

- Health data (heart rate, blood pressure, blood sugar, ECG, etc.) is transmitted in plaintext over BLE.
- Anyone with a BLE sniffer in range can capture and decode the protocol using the opcode table in `BLE_PROTOCOL.md`.
- The CRC16 polynomial is known (`0x8005`, from `ProtocolUtils.a()`).

---

## 🟡 Medium: Keep-Alive Aggressive Background Execution

The app uses multiple mechanisms to stay alive in background (see `ARCHITECTURE.md — Keep-Alive Strategy`):

1. **1-pixel Activity** — exploits screen-off broadcast to maintain foreground priority
2. **Dual-process service pair** (LocalService + RemoteService) — mutual resurrection
3. **JobScheduler** — scheduled wake-ups
4. **MAX_PRIORITY broadcast receiver** for phone calls

This behavior is common in Chinese Android apps targeting the local market where Google Play Services battery optimization doesn't apply.

---

## 🟡 Medium: Crash Log Exposure

`CrashHandlers.java` saves crash logs to device storage. If saved to external storage:
- Crash logs may contain stack traces with internal API paths, class names, or data.

---

## 🟢 Low: Obfuscation Level

The code is **lightly obfuscated** (ProGuard/R8 with class/method renaming):
- Most business logic classes retain meaningful names (`BleConnectService`, `ProtocolAppToDevice`, etc.)
- Only anonymous inner classes and helper methods are renamed to single letters (`a`, `b`, `c`, etc.)
- Constant values are fully intact
- All string literals are in plaintext (no string obfuscation)
- Chinese log strings are fully readable (e.g., `"电话挂断"` = "call hung up", `"蓝牙广播数据"` = "Bluetooth broadcast data")

---

## 🟢 Low: Debug Logging

The app uses a logging utility `f6.d` (obfuscated, but likely a thin wrapper over `android.util.Log`):
- Debug logs include raw BLE packet hex dumps
- Logs include device MAC addresses
- Logs include health sensor data values
- Log calls: `d.a()` = `Log.d()`, `d.c()` = `Log.w()`, `d.e()` = `Log.v()` (approximately)
- These logs are likely still present in release builds.

---

## Chinese Strings Found in Code (Log Messages)

These strings indicate app origin and internal developer context:

| Chinese | Translation |
|---------|-------------|
| `电话挂断` | Call hung up |
| `电话响铃` | Phone ringing |
| `正在通话` | In a call |
| `蓝牙广播数据` | Bluetooth broadcast data |
| `收到同屏数据` | Received same-screen data |
| `发送原始数据` | Sending raw data |
| `发送数据状态` | Send data status |
| `添加大发送数据` | Adding large send data |
| `升级完成` | Upgrade complete |
| `正在升级固件` | Upgrading firmware |
| `升级错误` | Upgrade error |
| `升级已暂停` | Upgrade paused |
| `准备就绪` | Ready |
| `蓝牙断开` | Bluetooth disconnected |
| `主机升级完成，等待连接副机` | Master OTA complete, waiting for slave connection |
| `是否支持2M` | Is 2M PHY supported |
| `音频数据读通道状态` | Audio data read channel status |
| `同屏数据读通道状态` | Same-screen data read channel status |
| `主读通道状态` | Main read channel status |
| `同屏写通道状态` | Same-screen write channel status |
| `中科OTA写通道状态无` | ZK (ZhuoKe) OTA write channel: none |
| `心率数据错误` | Heart rate data error |
| `收到来电时BLE连接状态` | BLE connection state when call received |
| `收到来电监听` | Received incoming call listener |
| `电话号码为空` | Phone number is empty |

---

## Permissions Required

Based on the code analysis, the app likely requests:
- `BLUETOOTH`, `BLUETOOTH_ADMIN`, `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` (BLE)
- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` (BLE scan + GPS)
- `READ_PHONE_STATE` (call monitoring)
- `READ_CONTACTS` (caller ID lookup)
- `RECEIVE_SMS` (SMS notifications)
- `CAMERA` (camera viewfinder feature)
- `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE` (file/photo storage)
- `NOTIFICATION_SERVICE` (notification listener)
- `RECEIVE_BOOT_COMPLETED` (auto-start on boot)
- `FOREGROUND_SERVICE` (keep-alive service)
- `INTERNET` (backend API calls)
- `ACCESS_NETWORK_STATE` (connectivity checks)
- `VIBRATE` (notifications)
