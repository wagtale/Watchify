# Watchify

Watchify is an open-source Android companion app for Bluetooth Low Energy (BLE) smartwatches. It replaces closed-source proprietary companion apps, offering a privacy-respecting, aesthetically premium, and fully-featured experience for your watch.

> See [CHANGELOG.md](CHANGELOG.md) for a full version history.

## Features

- **Liquid Glass UI:** A beautiful, visionOS-inspired "frosted glass" interface for the ultimate premium feel.
- **Robust Analytics Engine:** Pulls health metrics and computes a dynamic 0-100 General Health Score, flagging readings as Normal, Under, or Above standard medical thresholds.
- **Kafka-Style Data Processor:** Raw Bluetooth packets are parsed asynchronously via Kotlin Coroutines and indexed cleanly into an immutable SQLite database for fast, reliable data retrieval. 
- **Reverse-Engineered Protocol:** Fully decodes the undocumented BLE opcodes sent by the watch.
- **Weather \u0026 Notifications:** Built-in weather synchronization and notification push support to keep your watch up-to-date.

## Reverse-Engineered BLE Protocol

We have fully reverse-engineered the undocumented BLE data stream for these watch types. The watch communicates over a custom GATT characteristic using a 20-byte chunked protocol with a 10-byte header on the first fragment. 

*(Note: If you are looking at raw serial/UART dumps from the watch hardware, you may see `0xAB` and `0xBA` framing bytes. These are stripped by the watch's BLE chip before transmission and are **not** present in the over-the-air GATT protocol).*

### Full Protocol Opcode Map

Through decompilation and packet analysis, we have mapped the complete `ProtocolEnum` used by the watch firmware. This serves as the master list for anyone looking to build custom drivers or integrations:

> [!NOTE]
> *While all opcodes listed below exist in the decompiled firmware protocol map, many of the features marked as WIP (🚧) or Unsupported (❌) are yet to be proven as actively used or supported by the physical watch hardware. Some may be legacy artifacts or placeholders for different hardware SKUs.*

#### Health & Telemetry
| Status | Opcode | Name | Description |
|---|---|---|---|
| ✅ | `3` | `BATTERY_INFO` | Request/Receive battery percentage. |
| ✅ | `4` | `REAL_SPORT` | Real-time step/activity stream. |
| ✅ | `5` | `HISTORY_SPORT` | Bulk sync for historical steps. |
| ✅ | `6` | `SLEEP` | Sleep stage history and duration. |
| ✅ | `7` | `REAL_HEART_RATE` | Real-time BPM stream. |
| ✅ | `8` | `HISTORY_HEART_RATE` | Bulk sync for historical BPM. |
| ✅ | `17` | `EXERCISE_HEART_RATE` | BPM data tied to a specific workout. |
| ✅ | `18` | `BLOOD_PRESSURE` | Historical BP (Systolic/Diastolic). |
| ❌ | `19` | `ECG` | Electrocardiogram raw point data stream. |
| ✅ | `20` | `BLOOD_OXYGEN` | SpO2 percentage history. |
| ✅ | `24` | `REAL_TEMP` | Body temperature stream/history. |
| ✅ | `27` | `BLOOD_SUGAR` | Blood glucose history. |
| ❌ | `35` | `REAL_HRV` | Heart Rate Variability (Watch doesn't support it). |
| 🚧 | `133` | `MENSTRUAL_PERIOD_INFO` | Cycle tracking data. |
| ✅ | `149` | `AIR_PRESSURE_ALTITUDE` | GPS altitude and barometric pressure. |

#### Device Control & Setup
| Status | Opcode | Name | Description |
|---|---|---|---|
| ✅ | `1` | `AUTH_KEY` | Handshake sequence. |
| ✅ | `2` | `DEVICE_INFO` | Firmware version and hardware IDs. |
| ✅ | `9` | `DEV_SYNC` | Initial device state synchronization. |
| 🚧 | `10` | `SPORT MODE Data` | Sport mode BPM and Other data (Not fully implemented yet). |
| ✅ | `12` | `TIME_SYNC_REQ` | Watch requests time sync on connect. |
| 🚧 | `21` | `SENSOR_DATA_CONTROL` | Internal calibration command. |
| 🚧 | `22` | `FUNCTION_CONTROL` | Toggle watch features. |
| 🚧 | `23` | `AUDIO_BLE_MAC` | Bluetooth audio routing MAC request. |
| 🚧 | `25` | `RESTORE_FACTORY_SETTING` | Wipe device data. |
| ✅ | `52` | `DEVICE_AUDIO_STATE` | Control BT audio output route. |
| ✅ | `101` | `UNKNOWN_101` | Orphaned opcode. Spammed by watch during handshake but does not exist in OEM app source. |
| 🚧 | `102` | `USER_INFO` | Set age, weight, height. |
| 🚧 | `103` | `LANGUAGE_SETTING` | Change UI language. |
| ✅ | `104` | `TIME` | Sync Unix timestamp. |
| ✅ | `118` | `RESET` | Soft reboot. |
| ✅ | `119` | `SHUTDOWN` | Power off device. |
| ✅ | `120` | `PAIR_FINISH` | Handshake completion. |
| ✅ | `152` | `PHONE_AUDIO_STATE` | Control BT audio output route. |
| ✅ | `161` | `UNKNOWN_161` | Orphaned opcode. Emitted by watch but missing from OEM app source. |

#### Smart Features & Notifications
| Status | Opcode | Name | Description |
|---|---|---|---|
| ✅ | `11` | `FIND_PHONE_OR_DEVICE` | Trigger ringing/vibration. |
| ✅ | `14` | `MUSIC_CONTROL` | Play/Pause/Skip commands from watch. |
| 🚧 | `15` | `CALL_CONTROL_TO_APP` | Watch answering/rejecting call. |
| ✅ | `105` | `WEATHER` | Push weather forecasts to watch. |
| 🚧 | `106` | `ALARM_CLOCK` | Sync wake-up alarms. |
| ✅ | `107` | `MESSAGE_NOTICE` | Push SMS/App notifications. |
| ✅ | `110` | `DEV_SYNC_SETTINGS` | Synchronize settings bitmask. |
| ✅ | `113` | `MUSIC_METADATA` | Push track name and volume info. |
| 🚧 | `116` | `PHOTOGRAPH` | Remote camera shutter (WIP/Stripped due to Android security). |
| ✅ | `122` | `CALLS_SWITCH` | Toggle call notifications on watch. |
| ✅ | `124` | `APP_SWITCH` | Toggle app notifications on watch. |
| 🚧 | `131` | `DIAL_SYNC` | Custom watchface upload. |
| 🚧 | `135` | `ADDRESS_BOOK` | Sync favorite contacts. |
| ✅ | `140` | `WEATHER_PUSH` | Push weather conditions and UI data. |
| 🚧 | `150` | `MEDICINE` | Pill reminder schedules. |
| 🚧 | `154` | `AI_TEXT` | Push ChatGPT/AI response strings to UI. |

## Protocol Research

The [`research/`](research/) folder contains the full output of static analysis performed on the OEM companion app APK (`com.wtwd.utra`), as well as various Python scripts used to probe the OEM's web APIs and reverse-engineer the watch face binary structures. The APK was decompiled with JADX and the resulting source was used to map the complete undocumented BLE protocol.

Key documents:

| Document | Contents |
|----------|----------|
| [BLE_PROTOCOL.md](research/BLE_PROTOCOL.md) | Full packet framing spec, UUIDs, CRC16, opcode table |
| [FEATURES.md](research/FEATURES.md) | Complete feature inventory with associated opcodes |
| [DATA_MODEL.md](research/DATA_MODEL.md) | OEM database schema — all 35 tables and entity definitions |
| [CONSTANTS.md](research/CONSTANTS.md) | All enums — SportType, NoticeType, WeatherType, etc. |
| [SECURITY_NOTES.md](research/SECURITY_NOTES.md) | Security observations from the OEM app audit |
| [opcode_audit.md](research/opcode_audit.md) | Per-opcode audit cross-referenced with Watchify implementation |

See [research/README.md](research/README.md) for the full document index and methodology.

### Firmware (FOTA) Updates and Custom OS

During our research into the OEM's firmware update API, we discovered that the manufacturer's OTA infrastructure is fundamentally broken due to a misconfigured Amazon S3 bucket (`InvalidBucketName`). As a result, it is physically impossible to download official firmware updates (`.img` or `.ufw`) over the air for analysis. 

**Custom Watch Faces & Payloads:**
We successfully pulled custom Watch Face (`.bin`) binaries. We discovered that the app utilizes the exact same Bluetrum FOTA Bluetooth transmission protocol to push both Watch Faces and OS updates. The app performs zero cryptographic hash checks (like MD5 or SHA256) before flashing; it relies solely on rudimentary file length checks (e.g. comparing offset `0x30` or `0x00` against total file size).

Because there is zero cryptographic security on the payloads, it is theoretically possible to package and flash a custom OS (like FreeRTOS) over Bluetooth. However, due to the lack of hardware driver source code (display, radio, sensors) and the high risk of permanently hard-bricking the device without physical SWD/UART access, creating a custom OS is not currently pursued.

---

## Architecture

*   **`BleManager.kt`:** Handles the GATT connection, RX/TX subscriptions, and parses the 16-byte packet frames.
*   **`HealthDataProcessor.kt`:** A centralized event broker (using Coroutine `Channel` and `SharedFlow`) that writes incoming payload objects into `SQLite` and instantly broadcasts updates to the UI.
*   **`HealthAnalyticsEngine.kt`:** Evaluates indexed data against standard medical ranges to calculate insights and health scores.
*   **`WatchProtocol.kt`:** Constructs outbound `0xAB` command byte arrays.
*   **`MainActivity.kt`:** The primary Liquid Glass dashboard featuring dynamically rendered data graphs and bottom navigation.

## Tested Devices

Currently, the Watchify protocol implementation has been verified against the following hardware:

*   **Host Device:** Redmi Note 13 Pro 5G (Android 14)
*   **Watch Model:** *ZK-based Smartwatch (generic firmware)*

*If you successfully connect and sync data with another watch model, please open an issue or PR to add it to this list!*

## Security & Limitations

*   **Notification Interception:** Watchify parses incoming notifications (including 2FA and banking alerts) to forward them to the watch. This content is sent over the watch's standard unencrypted BLE channel. In `Debug` builds, notification text is briefly logged to the local Android Logcat for diagnostics.
*   **BLE Link Encryption:** The watch application-layer protocol does not support payload encryption. To secure your data stream over the air against interception, you **must** manually "Pair" (Bond) the watch in your Android system Bluetooth settings to enforce AES link-layer encryption.
*   **Database Access:** To protect sensitive metrics (heart rate, blood oxygen, sleep patterns, etc.), `adb backup` extraction is explicitly disabled. 

## Setup & Building

1. Clone this repository.
2. Create a `.env` file in the root directory and add your Windy API key:
   ```
   WINDY_API_KEY=your_api_key_here
   ```
3. Build the project using Gradle:
   ```bash
   ./gradlew assembleDebug
   ```

## Contributing

The Watchify BLE mapping provides a great foundation for porting to other open-source projects like [Gadgetbridge](https://gadgetbridge.org/). Pull requests for bug fixes, new opcodes, and UI enhancements are welcome!

## License

MIT License
