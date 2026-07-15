# Watchify

Watchify is an open-source Android companion app for Bluetooth Low Energy (BLE) smartwatches. It replaces closed-source proprietary companion apps, offering a privacy-respecting, aesthetically premium, and fully-featured experience for your watch.

## Features

- **Liquid Glass UI:** A beautiful, visionOS-inspired "frosted glass" interface for the ultimate premium feel.
- **Robust Analytics Engine:** Pulls health metrics and computes a dynamic 0-100 General Health Score, flagging readings as Normal, Under, or Above standard medical thresholds.
- **Kafka-Style Data Processor:** Raw Bluetooth packets are parsed asynchronously via Kotlin Coroutines and indexed cleanly into an immutable SQLite database for fast, reliable data retrieval. 
- **Reverse-Engineered Protocol:** Fully decodes the undocumented BLE opcodes sent by the watch.
- **Weather \u0026 Notifications:** Built-in weather synchronization and notification push support to keep your watch up-to-date.

## Reverse-Engineered BLE Protocol

We have fully reverse-engineered the undocumented BLE data stream for these watch types. The watch communicates over a custom GATT characteristic using a 16-byte fixed-header protocol.

- `0xAB` - Outbound prefix
- `0xBA` - Inbound prefix

### Uncovered Health Opcodes

| Opcode | Data Type | Parsing Logic |
|---|---|---|
| `3` | Fast Sync Request | Triggers the watch to dump stored history. |
| `5` | Steps | Incremental step counters. |
| `6` | Sleep | Sleep stages and duration. |
| `8` | Heart Rate | Standard BMP readings. |
| `18` | Blood Pressure | Encodes Systolic and Diastolic values. |
| `20` | Blood Oxygen (SpO2) | Percentage value. |
| `24` | Body Temperature | 16-bit Little-Endian, divide by 100 (e.g. `3620` -> `36.2 °C`). |
| `27` | Blood Glucose | 16-bit Little-Endian, divide by 100 (e.g. `619` -> `6.19 mmol/L`). |

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
