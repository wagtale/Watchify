# Protocol Research

This folder contains the full reverse-engineering output from static analysis of the OEM companion app APK (`com.wtwd.utra`). The APK was decompiled using JADX and the resulting Java source was analysed to produce the documents below.

## Documents

| File | Contents |
|------|----------|
| [BLE_PROTOCOL.md](BLE_PROTOCOL.md) | Complete BLE framing spec — service/characteristic UUIDs, packet layout, CRC16 algorithm, command/answer type enums, and full opcode table with directions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | OEM app architecture overview — service structure, BLE connection state machine, EventBus topology, and module breakdown |
| [FEATURES.md](FEATURES.md) | Full feature inventory — health monitoring, sport modes, device settings, notifications, and smart features with associated opcodes |
| [DATA_MODEL.md](DATA_MODEL.md) | GreenDAO ORM schema — all 35 database tables, entity field definitions, and health aggregation class descriptions |
| [CONSTANTS.md](CONSTANTS.md) | All extracted enums and constants — `SportType`, `NoticeType`, `RepeatWeek`, `AnswerType`, `WeatherType`, `TimeIntervalType`, etc. |
| [API_ENDPOINTS.md](API_ENDPOINTS.md) | Third-party API endpoints identified in the app — weather, geolocation, OTA update check |
| [EVENTBUS.md](EVENTBUS.md) | EventBus event class map — all inter-component communication events and their payload types |
| [SECURITY_NOTES.md](SECURITY_NOTES.md) | Security observations — cleartext transmission, lack of payload encryption, hardcoded credentials found in OEM app |


## Methodology

1. Obtained the OEM APK and extracted all `.dex` files.
2. Decompiled using JADX to Java source.
3. Analysed `com.wtwd.utra.ble.*`, `com.wtwd.utra.protocol.*`, and `com.wtwd.utra.data.*` packages.
4. Cross-referenced with live BLE packet captures to verify opcode behaviour.
5. Documented findings in this folder.

> **Note:** This research is for interoperability purposes. No proprietary binaries are redistributed here.
