# Watchify

Watchify is an open-source Android companion app for Bluetooth Low Energy (BLE) smartwatches. It replaces closed-source proprietary companion apps, offering a privacy-respecting, aesthetically premium, and fully-featured experience for your watch.

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

#### Health & Telemetry
| Opcode | Name | Description |
|---|---|---|
| `3` | `BATTERY_INFO` | Request/Receive battery percentage. |
| `4` | `REAL_SPORT` | Real-time step/activity stream. |
| `5` | `HISTORY_SPORT` | Bulk sync for historical steps. |
| `6` | `SLEEP` | Sleep stage history and duration. |
| `7` | `REAL_HEART_RATE` | Real-time BPM stream. |
| `8` | `HISTORY_HEART_RATE` | Bulk sync for historical BPM. |
| `17` | `EXERCISE_HEART_RATE` | BPM data tied to a specific workout. |
| `18` | `BLOOD_PRESSURE` | Historical BP (Systolic/Diastolic). |
| `19` | `ECG` | Electrocardiogram raw point data stream. |
| `20` | `BLOOD_OXYGEN` | SpO2 percentage history. |
| `24` | `REAL_TEMP` | Body temperature stream/history. |
| `26` | `HISTORY_TEMP` | Bulk sync for body temperature. |
| `27` | `BLOOD_SUGAR` | Blood glucose history. |
| `35` | `REAL_HRV` | Heart Rate Variability stream. |
| `133` | `MENSTRUAL_PERIOD_INFO` | Cycle tracking data. |

#### Device Control & Setup
| Opcode | Name | Description |
|---|---|---|
| `2` | `DEVICE_INFO` | Firmware version and hardware IDs. |
| `9` | `DEV_SYNC` | Initial device state synchronization. |
| `22` | `FUNCTION_CONTROL` | Toggle watch features. |
| `25` | `RESTORE_FACTORY_SETTING` | Wipe device data. |
| `102` | `USER_INFO` | Set age, weight, height. |
| `103` | `LANGUAGE_SETTING` | Change UI language. |
| `104` | `TIME` | Sync Unix timestamp. |
| `118` | `RESET` | Soft reboot. |
| `119` | `SHUTDOWN` | Power off device. |
| `120` | `PAIR_FINISH` | Handshake completion. |

#### Smart Features & Notifications
| Opcode | Name | Description |
|---|---|---|
| `11` | `FIND_PHONE_OR_DEVICE` | Trigger ringing/vibration. |
| `14` | `MUSIC_CONTROL` | Play/Pause/Skip commands from watch. |
| `15` | `CALL_CONTROL_TO_APP` | Watch answering/rejecting call. |
| `105` | `WEATHER` | Push weather forecasts to watch. |
| `106` | `ALARM_CLOCK` | Sync wake-up alarms. |
| `107` | `MESSAGE_NOTICE` | Push SMS/App notifications. |
| `116` | `PHOTOGRAPH` | Remote camera shutter trigger. |
| `131` | `DIAL_SYNC` | Custom watchface upload. |
| `135` | `ADDRESS_BOOK` | Sync favorite contacts. |
| `150` | `MEDICINE` | Pill reminder schedules. |
| `154` | `AI_TEXT` | Push ChatGPT/AI response strings to UI. |

## Architecture

*   **`BleManager.kt`:** Handles the GATT connection, RX/TX subscriptions, and parses the 16-byte packet frames.
*   **`HealthDataProcessor.kt`:** A centralized event broker (using Coroutine `Channel` and `SharedFlow`) that writes incoming payload objects into `SQLite` and instantly broadcasts updates to the UI.
*   **`HealthAnalyticsEngine.kt`:** Evaluates indexed data against standard medical ranges to calculate insights and health scores.
*   **`WatchProtocol.kt`:** Constructs outbound `0xAB` command byte arrays.
*   **`MainActivity.kt`:** The primary Liquid Glass dashboard featuring dynamically rendered data graphs and bottom navigation.

## Setup \u0026 Building

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
