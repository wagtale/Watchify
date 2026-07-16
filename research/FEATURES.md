# Features Inventory

Complete feature set of the WTWD Utra smartwatch companion app.

---

## Health Monitoring

| Feature | BLE Opcode | Notes |
|---------|-----------|-------|
| Real-time heart rate | `0x07` | Continuous polling |
| Historical heart rate | `0x08` | Synced on connect |
| 24-hour auto heart rate | `0x80` | On/off switch |
| Real-time blood oxygen (SpO2) | `0x14` | Manual trigger |
| Blood pressure monitoring | `0x12` | Manual trigger |
| ECG recording | `0x13` | Manual trigger |
| Real-time body temperature | `0x18` | Auto at intervals |
| Historical temperature | `0x1A` | Synced on connect |
| Temperature settings (interval, on/off) | `0x88` | |
| HRV (Heart Rate Variability) | `0x23` | Real-time |
| Sleep tracking (deep/light/wake/REM) | `0x06` | Auto nightly |
| Blood sugar monitoring | `0x1B` | Manual, pre/post meal |
| Blood sugar reference ranges | DB only | Per-meal thresholds |
| Pedometer / step count | `0x04`, `0x05` | Real-time + history |
| Exercise heart rate tracking | `0x11` | During sport session |

---

## Sport & Activity

| Feature | Notes |
|---------|-------|
| 34 sport modes | Run, Swim, Cycle, Yoga, Basketball, etc. (see DataEnum.SportType) |
| GPS sport tracking | Uses phone GPS, opcode `0x8C` |
| Real-time sport data | Steps, calories, distance, duration |
| Sport auto-pause | Configurable setting |
| Sport voice feedback | Text-to-speech announcements (AudioIDs) |
| Sport goals | Steps/calories/distance/time targets |
| Post-sport summary | Detailed stats + heart rate graph |
| Sport history | Full session list + replay |

### Full Sport Type List
breathe, cycling, indoor_cycling, running_machine, run, swim, walk, weight, yoga, badminton, basketball, skip, free_exercise, football, climbing, pingpong, bowling, openwater, dancing, dumbbells, hulohoop, stairsmove, stepper, triathlon, situps, ski, billiards, elliptical_machine, trail_running, aerobics, pilates, shuttlecock, spin, walking_machine

---

## Device Settings (App → Watch)

| Setting | BLE Opcode | Notes |
|---------|-----------|-------|
| Time sync | `0x68` | Unix timestamp + timezone offset |
| Time format | `0x79` | 12h/24h |
| Language | `0x67` | 30 languages supported |
| Unit settings | `0x79` | Distance, weight, temperature |
| Alarm clocks | `0x6A` | Up to N alarms with day-repeat |
| Sedentary reminder | `0x72` | Interval + time window |
| Drink reminder | `0x7E` | |
| Do Not Disturb | `0x73` | Time window |
| Hand-raise to wake | `0x7F` | Time window |
| Screen brightness | (device UI) | |
| SOS emergency number | `0x89` | |
| Target step/calorie goals | `0x6F` | |
| Target achievement reminder | `0x7D` | |
| User profile | `0x66` | Age/gender/height/weight/wearHand |
| Weather push | `0x69` | Up to 3-day forecast |
| Message switch (which apps) | `0x7C` | Per-app enable/disable |
| Medicine reminder | `0x96` | Up to N entries with times |
| Menstrual cycle tracking | `0x85` | |
| Sport mode config | `0x0A` | Which sport modes enabled on watch |

---

## Notifications

The app forwards phone notifications to the watch (opcode `0x6B`):

- **Supported apps**: Phone call, SMS, QQ, WeChat, Facebook, Twitter, WhatsApp, Instagram, Skype, LinkedIn, Line, Email, + custom/other
- **Call states**: Ringing → Answer/Reject/Mute (bidirectional control)
- **Music control**: Watch can control phone music player (play/pause/next/prev/volume)
- **Music content**: App pushes song title/artist to watch display

---

## Watch Face / Dial Management

| Feature | BLE Opcode | Notes |
|---------|-----------|-------|
| Dial list sync | `0x83` (`DIAL_SYNC`) | Push available dials |
| Dial info query | `0x84` (`DIAL_INFO`) | Get current dial info |
| Custom background | `0x83` | Photo as watch face (compressed) |
| Clock dial text color | `ClockDialTextColorBean` | |

Three background types: `DEFAULT (0)`, `SYSTEM (1)`, `CUSTOMIZE (2)`.

---

## AI Chat

| Feature | Notes |
|---------|-------|
| AI chat on watch | Text sent to watch via opcode `0x9A` |
| Baidu AI backend | ERNIE/文心一言 (key: `rh4s78cdvcw212a76`) |
| GPT backend | OpenAI GPT |
| Chunked transfer | 300-byte UTF-8 chunks with offset tracking |
| Chat history | Stored in `ChatMessageInfoDao` |

---

## Camera / Same-Screen Mirroring

| Feature | Notes |
|---------|-------|
| Phone camera viewfinder on watch | Uses `UUID_READ_SAME_SCREEN` + `UUID_WRITE_SAME_SCREEN` |
| Remote shutter trigger | Watch sends opcode `0x74`, app captures photo |
| Camera permission management | `CameraPresenter` + `RotationListener` |
| YUV→RGB conversion | `YuvToRgbConverter` for camera preview frames |
| Image analysis | `ImageAnalyzer` (likely CameraX) |

---

## QR Code Features

| Feature | Notes |
|---------|-------|
| Display QR on watch | Opcode `0x8A` (`DATA_TYPE_QR_CODE_DOWNLOAD`) |
| 14 QR code types | Business card, payments (Alipay/WeChat/PayPal/Google Pay), social profiles, health codes |
| QR code scanner | `QRCodeParseUtils` — parse incoming QR |

---

## Audio Features

| Feature | Notes |
|---------|-------|
| Bluetooth audio (A2DP companion) | `AudioBluetoothManager`, separate audio MAC (`PREF_KEY_AUDIO_MAC`) |
| Voice recording | `RecordOpusDecoder`, `WriteAudioHandler`, `OnRecordOpusCallback` |
| Opus codec | Audio from watch is decoded on phone |
| PCM streaming | `PCMStreamPlayer`, `PcmPlayer` |
| MP3 streaming | `Mp3StreamingAudioPlayer` |
| Sport voice prompts | Pre-recorded audio IDs (`AudioIDs`) |

---

## OTA Firmware Update

| Feature | Notes |
|---------|-------|
| ZK OTA | ZhuoKe OTA SDK (`com.bluetrum.fota`) via characteristic `b003` |
| Progress reporting | 0-100% with EventBus |
| Error handling | 20+ error codes |
| Dual-device support | Left/right earphone separate OTA |
| TWS (True Wireless Stereo) | Primary + secondary device sequential OTA |

---

## Account & Profile

| Feature | Notes |
|---------|-------|
| Phone number login | SMS verification code |
| Password login | Stored in SharedPrefs (plaintext!) |
| Tourist/guest mode | `PREF_KEY_TOURIST_ID` |
| Profile: gender, age, height, weight | Synced to watch |
| Wear hand preference | Left/right |
| Target steps | Daily goal |
| Country code picker | `CountryCodeDictionary` (international support) |
| Avatar/profile picture | Stored locally, `PREF_KEY_HEAD` |

---

## Map & Location

| Feature | Notes |
|---------|-------|
| Google Maps integration | For GPS sport routes |
| Gaofeng/AMap (高德) | Alternative Chinese map provider |
| GPS sport route recording | `GpsSportService` |
| Route locus display | `SportLocus`, `MyMapViewGoogle` |

---

## System / Utility Features

| Feature | Notes |
|---------|-------|
| Crash handler | `CrashHandlers` — saves crash logs |
| Custom fonts | `FontUtils` — loads fonts from assets |
| File utilities | `FileUtil` — SD card + internal storage |
| Image utilities | `ImageUtil`, `ImageUtil` |
| MD5 hashing | `MD5Utils` |
| AES encryption | `AESUtils` (stub/utility) |
| Date/time utilities | `DateUtils` |
| JSON utilities | `JsonUtils` |
| Language/locale | `LanguageUtils`, 30 language codes |
| Runtime permissions | `PermissionsUtil`, `RunPermissionUtil` |
| Country dictionary | `CountryDictionary`, `CountryCodeDictionary` |
| Character encoding | `CharacterParserUtils` (GB2312/Unicode conversion for watch display) |
| Unit conversion | `UnitUtil` (metric ↔ imperial) |

---

## Keep-Alive / Background Execution

| Mechanism | Class | Purpose |
|-----------|-------|---------|
| 1-pixel activity | `OnePixelActivity` | Keep process alive on screen-off |
| Foreground service | `HideForegroundService` | Persistent notification |
| JobScheduler service | `JobHandlerService` | Periodic task scheduling |
| Local + Remote service | `LocalService`, `RemoteService` | Dual-process resurrection |
| Boot receiver | `OnepxReceiver` | Start on boot |
| Screen state receiver | `OnepxReceiver` | React to screen on/off |
| Auto-reconnect | `NewsNotificationListenerService` | Reconnect BLE on BT on / app connect |
