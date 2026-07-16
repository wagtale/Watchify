# API Endpoints & Backend

Reverse engineered from `Constant.java`, `BaseApi.java`, `ChatHttpUtil.java`, and related files.

---

## Backend

### Base URL
```
https://wr.watchhealth.com.cn/app-halfwit/
```

The app communicates with this backend for:
- User account creation / login / token refresh
- Health data sync (upload)
- App version checking (`AppVersionDao`)
- Dial face / watch face asset downloads
- AI chat relay

---

## Hardcoded API Keys

| Key | Value | Used for |
|-----|-------|----------|
| `AI_KEY` | `rh4s78cdvcw212a76` | AI chat authentication |
| `GOOGLE_MAP_KEY` | `AIzaSyDFkGsF5bmlYTEA-oFeatd4MOzZnE7yz8w` | Google Maps SDK |
| `WEATHER_KEY` | `uqV3vCNsUuPgL7cNZ71AtNcFGVvRXViJ` | Weather service |
| `HUAWEI_MAP_KEY` | `DAEDAPlpeYvgTWACx3YzdGFhBmKXS3CPUat3BnGvxIKZAlB3B5u6RdnuDwd6YUeK8YZh7uVS9MYoHIWT89lx+XARE7uNa/zsKVyUEA==` | Huawei Map SDK |

---

## Auth Flow (SharedPrefs tokens)

Tokens stored in SharedPreferences under these keys:
- `PREF_KEY_ACCESS_TOKEN` — Bearer token
- `PREF_KEY_REFRESH_TOKEN` — Refresh token
- `PREF_KEY_OVER_TIME` — Token expiry timestamp
- `PREF_KEY_USER_ID` — Logged-in user ID
- `PREF_KEY_TOURIST_ID` — Guest/tourist session ID
- `PREF_KEY_ACCOUNT` — Stored account (phone/email)
- `PREF_KEY_PASSWORD` — **Stored plaintext password**
- `PREF_KEY_PHONE` — Phone number
- `PREF_KEY_LOGIN_TYPE` — Login type (phone/email/tourist)

> ⚠️ Password is stored in SharedPreferences without encryption.

---

## AI Chat Integration

Two AI backends are supported (selected by `PREF_KEY_CHAT_TYPE`):

| Value | Backend |
|-------|---------|
| `CHAT_TYPE_BAIDU` (21) | Baidu AI (文心一言 / ERNIE) |
| `CHAT_TYPE_GPT` (22) | OpenAI GPT |
| `CHAT_TYPE_SUCCESS` (23) | Chat succeeded |
| `CHAT_TYPE_FAIL` (24) | Chat failed |
| `CHAT_TYPE_NOT_INITIALIZED` (25) | Chat not set up |

The AI text is sent to the watch via BLE opcode `0x9A` (`DATA_TYPE_AI_TEXT`), chunked at 300-byte UTF-8 segments with offset tracking.

AI payload structure per chunk:
```
[0]     operation type
[1..4]  total text length (4 bytes)
[5..8]  byte offset of this chunk (4 bytes)
[9+]    UTF-8 text bytes (up to 300)
```

### `ChatHttpUtil` (HTTP utility)
Used for making chat API calls. Likely uses OkHttp or similar. Handles responses via `ResponseContent` entity with standard JSON payload.

---

## MVP API Layer

### `BaseApi.java`
Base class for all Retrofit/HTTP API calls. Uses:
- `ApiObserver` — wraps standard API response handling
- `BaseObserver` — RxJava observer base
- `ApiConsumer` — functional consumer for results
- `DeviceObserver` — observer for device-specific API responses
- `ApiFunction` — RxJava function for response mapping

### Response Model
```java
// ResponseContent.java
{
  data: Object,    // typed response data
  code: int,       // status code
  message: String  // human-readable status
}
```

---

## Notification Mapping (App Packages → Device)

Hardcoded in `NewsNotificationListenerService.onListenerConnected()`:

| Package Name | Notice Type ID | Social App |
|---|---|---|
| `com.android.incallui` | 1 | Phone Call |
| `com.android.mms` | 2 | SMS |
| `com.tencent.mobileqq` | 3 | QQ |
| `com.tencent.mm` | 4 | WeChat |
| `com.facebook.katana` | 6 | Facebook |
| `com.twitter.android` | 7 | Twitter/X |
| `com.whatsapp` | 8 | WhatsApp |
| `com.instagram.android` | 9 | Instagram |
| `com.skype.raider` | 10 | Skype |
| `com.linkedin.android` | 11 | LinkedIn |
| `jp.naver.line.android` | 12 | Line |
| (any `.mail` suffix or `com.google.android.gm`) | 5 | Email |
| (all others) | 13 | Other |

Special handling: `com.android.dialer` and `com.google.android.dialer` are treated as phone call sources.
SMS special-cased for Xiaomi (`Build.MANUFACTURER.equals("Xiaomi")`) — skips empty ticker.

---

## Weather API Integration

Weather key `uqV3vCNsUuPgL7cNZ71AtNcFGVvRXViJ` is used to query a weather service (likely Caiyun/ColorfulClouds API based on Chinese key naming conventions).

Data is sent to device via opcode `0x69` with up to 3-day forecast:
- Weather type code (see `DataEnum.WeatherType`)
- Low temperature
- High temperature

---

## Location Services

Two location providers supported:
- **GaoFeng** (`GaoFengLocation`, `GaoFengLocationInfo`) — Chinese high-precision GPS (likely AMap/高德)
- **Google** (`GoogleLocation`) — Standard Google Location Services

GPS data sent to device via opcode `0x8C` (`DATA_TYPE_GPS`).

---

## QR Code Types (for watch display)

| Value | QR Type |
|-------|---------|
| 0 | NULL |
| 1 | NAME_CARD |
| 2 | PAY_ALIPAY |
| 3 | PAY_WECHAT |
| 4 | PAY_PAYPAL |
| 5 | PAY_GOOGLE |
| 6 | FRIEND_QQ |
| 7 | FRIEND_WECHAT |
| 8 | FRIEND_FACEBOOK |
| 9 | FRIEND_TWITTER |
| 10 | FRIEND_WHATS_APP |
| 11 | FRIEND_INSTAGRAM |
| 12 | OTHER |
| 13 | HEALTH_CODE |
| 14 | NUCLEIN_CODE |
