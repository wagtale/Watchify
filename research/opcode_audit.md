# Watchify Opcode Audit

I have thoroughly audited both `BleManager.kt` (for incoming RX opcodes) and `WatchProtocol.kt` (for outgoing TX commands) and cross-referenced them with your `README.md`. 

Here are the discrepancies and findings:

### 1. Marked Integrated (✅) in README but MISSING in Code
*   **`26` (`HISTORY_TEMP`)**: Marked as ✅ in the README, but it is completely missing from both `BleManager.kt` and `WatchProtocol.kt`. We are not requesting or parsing bulk body temperature history.

### 2. Marked Work-in-Progress (🚧) in README but INTEGRATED in Code
*   **`24` (`REAL_TEMP`)**: Marked as 🚧, but we actually *do* request it via `buildFastSyncRequests()` in `WatchProtocol.kt` and parse it in `BleManager.kt`. 

### 3. Marked Dead/Fake (❌) in README but STILL in Code
*   **`110` (`APP_SYNC`)**: Marked as ❌ in the README. While you successfully stripped it from `BleManager.kt`, the function `buildAppSyncPayload` still exists in `WatchProtocol.kt` (line 56) constructing this opcode. We should probably remove it.

### 4. Fully Implemented in Code but MISSING from README
These opcodes are actively used in our app but aren't documented in the protocol map in the README at all:
*   **`113` (Music Metadata Push)**: We send this from `BleManager.kt` to push the current playing song title and volume.
*   **`122` (Call Switch Toggle)**: We send this from `MainActivity.kt` when the user flips the "Sync Calls" switch.
*   **`124` (App Notice Switch Toggle)**: We send this from `MainActivity.kt` when the user flips the "App Alerts" switch.
*   **`140` (Weather Push)**: Sent twice from `MainActivity.kt` for weather sync, likely an extended weather payload alongside `105`.
*   **`1`, `10`, `21`, `23`, `101`, `161`**: We have handler logic or ACK catchers for all of these inside `BleManager.kt`, but their exact names and purposes aren't defined in the README.

---
**Recommendation:** We should clean up `WatchProtocol.kt` by removing Opcode `110`, remove Opcode `26` from the README (or actually implement it), and add the missing opcodes (`113`, `122`, `124`, `140`) to the README's documentation.
