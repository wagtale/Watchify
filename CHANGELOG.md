# Changelog

All notable changes to Watchify are documented here, ordered newest-first.
Versions are tagged in Git; entries without a tag number are unreleased or hotfix commits.

---

## [v1.0.54] — 2026-07-16
### Added
- **Inbound opcode logging** — every packet received from the watch now logs a single line in the debug console: `[←] Opcode N (NAME) Xb`. Shows the opcode number, human-readable name from the full `ProtocolEnum`, and payload byte count. No health data or personal content is included.
- `opcodeLabel()` lookup covers all 35 known opcodes including ACK responses (`HEART_AUTO_SWITCH_ACK=128`, `TEMP_SETTING_ACK=136`) so auto-monitoring confirmation is now visible immediately after connect.

---

## [v1.0.53] — 2026-07-16
### Fixed
- **`0x80` heart auto switch payload wrong** — was sending 1 byte `[0x01]`; OEM source (`AutomaticHeartModel.java`) shows the watch requires **8 bytes**: `[state, state, 0, 0, 0, 0, 0, 0]` (state duplicated at bytes 0 and 1, rest zeroed). Watch was silently ignoring the malformed 1-byte packet so 24h auto HR was never actually enabled.
- **`0x88` temp setting payload wrong** — was sending 2 bytes; OEM source (`TemperatureSettingModel.java`) shows it must be **3 bytes**: `[switch, intervalLo, intervalHi]` with the interval in minutes as a 2-byte little-endian integer. Default is 10 minutes (matching OEM default).
### Added
- **Emoji → ASCII mapping in notifications** — the watch display is GBK only; emoji code points (U+1F300+) are not encodable and were corrupting the watch notification UI. Common emojis now map to ASCII equivalents (`❤️`→`<3`, `👍`→`(+1)`, `🔥`→`(fire)`, `😊`→`:)`, `😢`→`:(`, etc.); all other supplementary plane characters are stripped before encoding.

---

## [v1.0.50] — 2026-07-16
### Fixed
- **Auto-monitoring packets sent but watch settings reset on reconnect** — watch resets all monitoring configuration on every new connection. Added `buildHeartAutoSwitchPacket()` (opcode `0x80`) and `buildTempMonitoringPacket()` (opcode `0x88`) and wired them into the post-connect sync sequence so they are sent on every connection.

---

## [v1.0.50] — 2026-07-16
### Fixed
- **Auto-monitoring never enabled on connect** — the watch resets all monitoring settings on reconnect and was never told to start background health checks, so data only appeared when the user manually triggered a reading on the watch face.
- `WatchProtocol`: add `buildHeartAutoSwitchPacket()` for opcode `0x80` (`DATA_TYPE_HEART_AUTO_SWITCH`) — enables 24-hour continuous heart rate monitoring; watch now streams BPM automatically every few minutes.
- `WatchProtocol`: add `buildTempMonitoringPacket()` for opcode `0x88` (`DATA_TYPE_TEMP_SETTING`) — enables automatic body temperature readings at 5-minute intervals.
- `BleManager`: both packets are now sent immediately after settings sync on every connection.

---

## [v1.0.49] — 2026-07-16
### Fixed
- **Zero-value health data polluting graphs** — the watch sends `0.0`-padded placeholder records for time slots where no measurement was taken; these were being written to SQLite and corrupting graph history.
- `HealthDataProcessor`: added `isValid()` guard in `pushRecord()` — records are rejected before reaching the database if their primary value is zero or falls outside a physiologically plausible range. Per-type limits derived from real medical bounds (e.g. HR must be 30–250 bpm, SpO2 50–100%, temp 30–45 °C).

---

## [v1.0.48] — 2026-07-16
### Fixed
- **Glitchy PixelCopy blur** — the async PixelCopy approach caused visible lag, feedback ghosting (glass appearing in its own blur), and frame-timing artifacts during scroll.
- `GlassView`: replaced PixelCopy + background thread blur pipeline with `RenderEffect.createBlurEffect()` (API 31+) — GPU-accelerated, frame-synchronous, zero lag, no feedback loop.
- Clean semi-transparent dark fill provides the frosted appearance; plain overlay fallback on API <31.

---

## [v1.0.47] — 2026-07-16
### Refactored
- `GlassView`: stripped all decorative layers (shimmer, specular highlight, inner shadow, border stroke) added in v1.0.46 per user preference. Now just a clean 50% blur (radius 12) of captured background content.

---

## [v1.0.46] — 2026-07-15
### Added
- **iOS 26-style Liquid Glass effect** on header and bottom navigation bars.
- `GlassView` complete rewrite: six composited layers — blurred real background (PixelCopy), dark tinted glass body, top specular edge highlight, animated iridescent shimmer sweep (icy blue/rose, 5.5 s loop), bottom inner shadow, gradient border stroke.
- `invalidateBlur()` debounced at 120 ms and wired to scroll listeners so the blur tracks scrolled content accurately.
- Proper lifecycle management: animator paused on detach, bitmap recycled, Handler cleared.

---

## [v1.0.45] — 2026-07-15
### Fixed
- **Health graphs blank on cold open** — `updateHealthGraph()` and `updateAnalyticsView()` were called before `GraphView`/`TextView` widgets were initialised; `isInitialized` guards blocked all rendering.
- `MainActivity`: moved initial render calls to after `setContentView()`.
- `MainActivity`: added both calls to `onResume()` — graphs now refresh from SQLite every time the user returns to the app.
- `WatchDriverService`: added `startHealthSync()` background loop — requests a fast health data dump from the watch every 10 minutes while the service is running, keeping SQLite current even when the activity is closed.

---

## [v1.0.44] — 2026-07-15
### Fixed — Protocol correctness, reliability, and UX
- `WatchProtocol`: removed SMS switch (`0x7B`) from composite `DEV_SYNC_SETTINGS` packet (opcode `0x6E`) — it was causing sub-packet framing corruption; now sent as a standalone opcode 123 packet.
- `WatchProtocol`: sub-packet count is now dynamic (was hardcoded to 8).
- `WatchProtocol`: notification title encoding corrected to GBK charset with UTF-8 fallback (raw `char.code.toByte()` was silently corrupting non-ASCII characters).
- `WatchProtocol`: added `buildBle50SupportPacket()` (opcode 29) and `buildExtPidPacket()` (opcode 31) for watch feature negotiation.
- `WatchProtocol`: removed dead code — `FULL_BIND_PAYLOAD`, `buildSecurePacket`, `buildPaddedPacket`.
- `BleManager`: all fire-and-forget `CoroutineScope(IO).launch` replaced with a lifecycle-scoped `SupervisorJob` scope; `cancelChildren()` called on `disconnect()` to prevent dangling BLE writes.
- `BleManager`: BLE 5.0 and EXT_PID negotiation packets sent after handshake.
- `BleManager`: opcode 9 (`DEV_SYNC`) payload now parsed — logs firmware version, hardware revision, BLE MAC, and device name.
- `BleManager`: blood glucose meal-type byte preserved in `HealthRecord.value2` (was discarded).
- `NotificationMonitor`: fallback app ID corrected from 12 → 13 — all unknown apps were mapping to the LINE messenger icon.
- `NotificationMonitor`: display title threshold updated to match corrected app ID enum.
- `WeatherManager`: `ipapi.co` JSON field names corrected — was checking non-existent `"status"` field; IP geolocation fallback was silently failing on every call.
- `MainActivity`: battery poll interval reduced from 10 s to 60 s to reduce BLE congestion.
- `MainActivity`: sleep type display now shows human-readable labels (Deep / Light / Awake) instead of raw float values.
- `MainActivity`: `bleManager?.let` on a `lateinit` replaced with `isInitialized` guard.
- `MainActivity`: `autoSync while(true)` corrected to use `delay()` as the cancellation point (idiomatic coroutine pattern).
- `MainActivity`: `HEALTH_DATA_UPDATED` and `CITY_UPDATED` added to `onResume` broadcast filter.
- `MainActivity`: `applySwitchesBtn` now sends SMS switch as standalone opcode 123.
- `GlassView`: removed unsafe `target.draw(canvas)` call on hardware-accelerated view — crash risk on API 31+; `RenderEffect` handles blur natively.

---

## [v1.0.43] — 2026-07-14
### Docs
- Added note to README about unproven WIP opcodes — several opcodes listed exist in the decompiled firmware protocol map but have not been verified as actively used by the physical hardware.

---

## [v1.0.42] — 2026-07-14
### Added
- CSV health data export via `HealthDataProcessor.exportToCsv()`.
- Tested devices section in README.
- GitHub Actions CI workflow for automated APK builds.

---

## [v1.0.41] — 2026-07-14
### Security
- Migrated IP geolocation API calls from HTTP to HTTPS to prevent cleartext data leakage.

---

## [v1.0.40] — 2026-07-14
### Security
- Migrated hardcoded signing credentials out of `build.gradle` into a gitignored `keystore.properties` file.
- Rotated the release keystore.

---

## [v1.0.39] — 2026-07-14
### Docs
- Added BLE bonding instructions to Security & Limitations section of README — users must manually bond in Android Bluetooth settings to enforce AES link-layer encryption.

---

## [v1.0.38] — 2026-07-14
### Security
- Restricted debug logging — sensitive notification content no longer logged outside of debug builds.
- Disabled `adb backup` extraction to protect on-device health database.

---

## [v1.0.37] — 2026-07-14
### Docs
- Fully audited and synchronised README opcode table with the actual codebase implementation status.

---

## [v1.0.36] — 2026-07-14
### Fixed
- Opcode 9 (`DEV_SYNC`) was falling through to the unknown hex dump handler, producing noisy log output. Now caught and processed correctly.

---

## [v1.0.35] — 2026-07-14
### Fixed
- Removed reference to non-existent `ic_power` drawable that caused resource resolution crash.

---

## [v1.0.34] — 2026-07-14
### Fixed
- `HealthDataProcessor` initialised globally in `WatchApplication` to prevent data loss when background BLE sync arrives before the Activity is created.

---

## [v1.0.33] — 2026-07-14
### Fixed
- `HealthDataProcessor` SharedFlow updates now correctly propagate to the analytics engine and trigger UI re-renders.

---

## [v1.0.32] — 2026-07-14
### Fixed
- `HealthDatabaseHelper.onUpgrade()` now migrates existing data into the new schema instead of dropping the table — health records are preserved across version upgrades.

---

## [v1.0.30] — 2026-07-13
### Removed
- Stripped experimental camera shutter spoofing feature — the approach required Accessibility Service privileges and unreliable audio focus hacks that were too fragile for production.

---

## [v1.0.29] — 2026-07-13
### Added
- Accessibility Service implementation to tap the on-screen camera shutter button as a more reliable shutter trigger approach.

---

## [v1.0.28] — 2026-07-13
### Fixed
- Improved camera shutter spoofing reliability using AudioFocus + PlayPause + Volume trick combination.

---

## [v1.0.27] — 2026-07-13
### Fixed
- Version code now incremented automatically when uncommitted changes exist in the working tree.

---

## [v1.0.26] — 2026-07-13
### Fixed
- Disabled watch audio routing during shutter spoof to make the remote camera trigger completely silent.

---

## [v1.0.25] — 2026-07-13
### Added
- Liquid glass melt-away scroll animation on the header bar — header slides out with an Anticipate interpolator on scroll-down, bounces back with Overshoot on scroll-up.

---

## [v1.0.24] — 2026-07-13
### Added
- Headset hook simulation for remote camera shutter — triggers the phone camera via BLE watch button press using `AudioManager` media button injection.

---

## [v1.0.23] — 2026-07-13
### Added
- Opcode 116 (`PHOTOGRAPH`) handler for camera control commands from the watch.

---

## [v1.0.22] — 2026-07-13
### Added
- Opcode 149 (`AIR_PRESSURE_ALTITUDE`) — syncs GPS altitude and barometric pressure to the watch using the `pressure = (101.32 - 0.011 × altitude) × 100` formula.

---

## [v1.0.21] — 2026-07-13
### Added
- Dynamic mapping of all 100+ sport type IDs from the `SportType` enum to human-readable strings.

---

## [v1.0.20] — 2026-07-13
### Added
- Opcode 10 sport mode summary parsing — BPM and session data extracted from sport mode packets.

---

## [v1.0.19] — 2026-07-13
### Added
- Debug log console is now scrollable with an increased line limit.

---

## [v1.0.18] — 2026-07-13
### Added
- Unknown opcode handler now dumps the full raw hex payload to the debug log for easier protocol investigation.

---

## [v1.0.17] — 2026-07-13
### Added
- Opcode 35 (`REAL_HRV`) parsing for Heart Rate Variability data (hardware support varies by watch model).

---

## [v1.0.16] — 2026-07-13
### Added
- Estimated active calorie calculation based on step count, user weight, and activity duration, surfaced in the health dashboard.

---

## [v1.0.15] — 2026-07-13
### Added
- Opcode 17 (`EXERCISE_HEART_RATE`) parser — heart rate data tied to specific workout sessions.

---

## [v1.0.14] — 2026-07-13
### Added
- Dynamic battery icon updates — icon reflects current battery percentage from opcode 3 responses.

---

## [v1.0.13] — 2026-07-13
### Fixed
- Restored edge-to-edge transparency by adjusting individual child view padding instead of the root layout, preserving the transparent status/nav bar look.

---

## [v1.0.12] — 2026-07-13
### Fixed
- Header clipping on devices with a display cutout — `mainRootLayout` now insets by the cutout height.

---

## [v1.0.11] — 2026-07-13
### Changed
- Immersive mode enabled; navigation bar hidden with swipe-to-reveal behaviour (`BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE`).
- Dynamic padding applied so content respects system bar insets.

---

## [v1.0.10] — 2026-07-13
### Changed
- Edge-to-edge window rendering enabled via `WindowCompat.setDecorFitsSystemWindows(false)`.
- Status and navigation bar colours set to transparent.

---

## [Pre-release] — Initial development
### Added
- Initial commit: reverse-engineered BLE companion app for ZK-based smartwatches.
- Full `ProtocolEnum` opcode map documented in README.
- Clarification of BLE GATT over-the-air framing vs UART `0xAB`/`0xBA` framing (UART bytes are stripped by the BLE chip and are not present over-the-air).
- Apple system blue colour applied to health data elements.
- Watch icon updated via IconKitchen.
- Release signing and ProGuard obfuscation configured.
- Notification access permission UI and dynamic build versioning added.
- Unpolished/experimental features moved to `DebugActivity`.
- Auto-prompt for notification access on first launch.
