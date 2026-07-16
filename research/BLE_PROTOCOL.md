# BLE Protocol Analysis

Reverse engineered from `com.wtwd.utra.ble.*` and `com.wtwd.utra.protocol.*`

---

## BLE Service & Characteristic UUIDs

All characteristics are under a single service:

| Role | UUID |
|------|------|
| **Service** | `0000e91a-0000-1000-8000-00805f9b34fb` |
| **Write (main)** | `0000b002-0000-1000-8000-00805f9b34fb` |
| **Read (main notify)** | `0000b001-0000-1000-8000-00805f9b34fb` |
| **Write ZK OTA** | `0000b003-0000-1000-8000-00805f9b34fb` |
| **ZK notify** | `0000b005-0000-1000-8000-00805f9b34fb` |
| **Read Audio** | `0000b006-0000-1000-8000-00805f9b34fb` |
| **Read Same-Screen** | `0000b008-0000-1000-8000-00805f9b34fb` |
| **Write Same-Screen** | `0000b009-0000-1000-8000-00805f9b34fb` |
| **CCCD (descriptor)** | `00002902-0000-1000-8000-00805f9b34fb` |

**Note:** The app enables notifications on `b001` (main data), `b006` (audio), and `b008` (same-screen mirroring). The CCCD descriptor `00002902` is written with `ENABLE_NOTIFICATION_VALUE` for the main read channel.

After service discovery the app requests **MTU = 245**. If the negotiated MTU > 245, it caps at 240; otherwise uses `mtu - 5`.

---

## Packet Framing — App → Device

`ProtocolAppToDevice.g(int cmdType, int cmdSendType, int dataType, byte[] payload)`

Packet layout (each frame is 20 bytes due to BLE ATT default; chunked into N×20):

```
Offset  Byte    Meaning
------  ----    -------
  0     0x00    Fixed header / SOF
  1     pid     Platform/device PID
  2     N       Continuation packet count (ceil(payloadLen-10)/19)
  3     cmdType Command type (see CmdType enum)
  4     sendType Send mode (see CmdType)
  5     dataType Data type opcode (see DataType enum)
  6-7   0x00 0x00  Reserved / CRC placeholder
  8-9   payload length (2 bytes, big-endian)
 10+    First 10 bytes of payload
```

Continuation frames (for payload > 10 bytes):
```
[prev_frame + 20n + 0] = continuation index (1-based)
[prev_frame + 20n + 1..19] = next 19 bytes of payload
```

CRC16 calculation (`ProtocolUtils.a(byte[])`): XOR-based, polynomial `0x8005`, 16-bit.

---

## Command Types (`ProtocolEnum.CmdType`)

| Name | Value | Meaning |
|------|-------|---------|
| `CMD_TYPE_NULL` | 0 | No command |
| `CMD_TYPE_SEND` | 1 | Send with ACK |
| `CMD_TYPE_SEND_NO_ACK` | 2 | Fire and forget |
| `CMD_TYPE_REQUEST` | 3 | Request from app |
| `CMD_TYPE_ANSWER` | 4 | Answer/reply |

---

## Answer Types (`ProtocolEnum.AnswerType`)

| Name | Value |
|------|-------|
| `ANSWER_TYPE_NULL` | 0 |
| `ANSWER_TYPE_SUCCESS` | 1 |
| `ANSWER_TYPE_WRONG` | 2 |
| `ANSWER_TYPE_CRC16_WRONG` | 3 |
| `ANSWER_TYPE_OVER` | 4 |

---

## Data Type Opcodes (`ProtocolEnum.DataType`) — Complete List

These are the `dataType` byte in packet offset 5:

| Opcode (dec) | Hex | Name | Direction |
|---|---|---|---|
| 2 | 0x02 | `DATA_TYPE_DEVICE_INFO` | Dev→App |
| 3 | 0x03 | `DATA_TYPE_BATTERY_INFO` | Dev→App |
| 4 | 0x04 | `DATA_TYPE_REAL_SPORT` | Dev→App |
| 5 | 0x05 | `DATA_TYPE_HISTORY_SPORT` | Dev→App |
| 6 | 0x06 | `DATA_TYPE_SLEEP` | Dev→App |
| 7 | 0x07 | `DATA_TYPE_REAL_HEART_RATE` | Dev→App |
| 8 | 0x08 | `DATA_TYPE_HISTORY_HEART_RATE` | Dev→App |
| 9 | 0x09 | `DATA_TYPE_DEV_SYNC` | Bidirectional |
| 10 | 0x0A | `DATA_TYPE_SPORT_MODE` | App→Dev |
| 11 | 0x0B | `DATA_TYPE_FIND_PHONE_OR_DEVICE` | Bidirectional |
| 14 | 0x0E | `DATA_TYPE_MUSIC_CONTROL` | Dev→App |
| 15 | 0x0F | `DATA_TYPE_CALL_CONTROL_TO_APP` | Dev→App |
| 17 | 0x11 | `DATA_TYPE_EXERCISE_HEART_RATE` | Dev→App |
| 18 | 0x12 | `DATA_TYPE_BLOOD_PRESSURE` | Dev→App |
| 19 | 0x13 | `DATA_TYPE_ECG` | Dev→App |
| 20 | 0x14 | `DATA_TYPE_BLOOD_OXYGEN` | Dev→App |
| 21 | 0x15 | `DATA_TYPE_SENSOR_DATA_CONTROL` | App→Dev |
| 22 | 0x16 | `DATA_TYPE_FUNCTION_CONTROL` | App→Dev |
| 23 | 0x17 | `DATA_TYPE_AUDIO_BLE_MAC` | App→Dev |
| 24 | 0x18 | `DATA_TYPE_REAL_TEMP` | Dev→App |
| 25 | 0x19 | `DATA_TYPE_RESTORE_FACTORY_SETTING` | App→Dev |
| 26 | 0x1A | `DATA_TYPE_HISTORY_TEMP` | Dev→App |
| 27 | 0x1B | `DATA_TYPE_BLOOD_SUGAR` | Dev→App |
| 29 | 0x1D | `DATA_TYPE_SUP_BLE_50` | App→Dev |
| 31 | 0x1F | `DATA_TYPE_EXT_PID` | App→Dev |
| 35 | 0x23 | `DATA_TYPE_REAL_HRV` | Dev→App |
| 51 | 0x33 | `DATA_TYPE_DEV_TYPE` | Dev→App |
| 52 | 0x34 | `DATA_TYPE_DEVICE_AUDIO_STATE` | Dev→App |
| 102 | 0x66 | `DATA_TYPE_USER_INFO` | App→Dev |
| 103 | 0x67 | `DATA_TYPE_LANGUAGE_SETTING` | App→Dev |
| 104 | 0x68 | `DATA_TYPE_TIME` | App→Dev |
| 105 | 0x69 | `DATA_TYPE_WEATHER` | App→Dev |
| 106 | 0x6A | `DATA_TYPE_ALARM_CLOCK` | App→Dev |
| 107 | 0x6B | `DATA_TYPE_MESSAGE_NOTICE` | App→Dev |
| 109 | 0x6D | `DATA_TYPE_SENSOR_DATA_SWITCH` | App→Dev |
| 110 | 0x6E | `DATA_TYPE_APP_SYNC` | App→Dev |
| 111 | 0x6F | `DATA_TYPE_SET_TARGET` | App→Dev |
| 113 | 0x71 | `DATA_TYPE_MUSIC_CONTENT` | App→Dev |
| 114 | 0x72 | `DATA_TYPE_SEDENTARY_REMIND` | App→Dev |
| 115 | 0x73 | `DATA_TYPE_NOT_DISTURB_MODE` | App→Dev |
| 116 | 0x74 | `DATA_TYPE_PHOTOGRAPH` | Bidirectional |
| 117 | 0x75 | `DATA_TYPE_CALL_CONTROL_TO_DEV` | App→Dev |
| 118 | 0x76 | `DATA_TYPE_RESET` | App→Dev |
| 119 | 0x77 | `DATA_TYPE_SHUTDOWN` | App→Dev |
| 120 | 0x78 | `DATA_TYPE_PAIR_FINISH` | App→Dev |
| 121 | 0x79 | `DATA_TYPE_UNIT_SETTING` | App→Dev |
| 122 | 0x7A | `DATA_TYPE_CALL_REMIND` | App→Dev |
| 123 | 0x7B | `DATA_TYPE_SMS_REMIND` | App→Dev |
| 124 | 0x7C | `DATA_TYPE_MESSAGE_SWITCH` | App→Dev |
| 125 | 0x7D | `DATA_TYPE_TARGET_REMIND` | App→Dev |
| 126 | 0x7E | `DATA_TYPE_DRINK_REMIND` | App→Dev |
| 127 | 0x7F | `DATA_TYPE_HAND_RISE_SWITCH` | App→Dev |
| 128 | 0x80 | `DATA_TYPE_HEART_AUTO_SWITCH` | App→Dev |
| 130 | 0x82 | `DATA_TYPE_APP_SPORT` | App→Dev |
| 131 | 0x83 | `DATA_TYPE_DIAL_SYNC` | App→Dev |
| 132 | 0x84 | `DATA_TYPE_DIAL_INFO` | Bidirectional |
| 133 | 0x85 | `DATA_TYPE_MENSTRUAL_PERIOD_INFO` | App→Dev |
| 135 | 0x87 | `DATA_TYPE_ADDRESS_BOOK` | App→Dev |
| 136 | 0x88 | `DATA_TYPE_TEMP_SETTING` | App→Dev |
| 137 | 0x89 | `DATA_TYPE_SOS_NUMBER_SETTING` | App→Dev |
| 138 | 0x8A | `DATA_TYPE_QR_CODE_DOWNLOAD` | App→Dev |
| 140 | 0x8C | `DATA_TYPE_GPS` | App→Dev |
| 149 | 0x95 | `DATA_TYPE_AIR_PRESSURE_ALTITUDE` | App→Dev |
| 150 | 0x96 | `DATA_TYPE_MEDICINE` | App→Dev |
| 152 | 0x98 | `DATA_TYPE_PHONE_AUDIO_STATE` | Dev→App |
| 153 | 0x99 | `DATA_TYPE_PHONE_AUDIO_WAKE` | Dev→App |
| 154 | 0x9A | `DATA_TYPE_AI_TEXT` | App→Dev |
| 201 | 0xC9 | `DATA_TYPE_OTA_STATUS` | Bidirectional |
| 202 | 0xCA | `DATA_TYPE_OTA_DATA` | App→Dev |
| 203 | 0xCB | `DATA_TYPE_TEST_DEBUG` | App→Dev |
| 205 | 0xCD | `DATA_TYPE_APP_TEST` | App→Dev |

---

## App→Device Payload Details (selected)

### Alarm Clock (0x6A)
```
[0]        count (number of alarms)
[1+n*5+0]  alarm index/id
[1+n*5+1]  hour
[1+n*5+2]  minute
[1+n*5+3]  repeat bitmask (see RepeatWeek enum)
[1+n*5+4]  enabled flag
```

### Time Sync (0x68)
```
[0..3]  Unix timestamp in seconds (4 bytes big-endian)
[4..7]  Timezone offset in seconds (4 bytes big-endian)
[8]     Extra flag (& 0xFF)
```

### Weather (0x69)
```
[0..3]  Timestamp (4 bytes)
Per weather entry (up to 3):
  [4+n*5+0]  weather type code (see WeatherType enum)
  [4+n*5+1]  low temperature
  [4+n*5+2]  high temperature
```

### Message Notification (0x6B)
```
[0..3]  Timestamp (4 bytes)
[4]     Notice type (see NoticeType enum)
[5]     Content item count
Per content item:
  [0]   encoding: 1=unicode/GB, 0=UTF-8
  [1]   length
  [n]   content bytes
```

### Call Control to Device (0x75)
```
[0]  call control type:
       1 = ANSWER_CALL
       2 = HANGUP_CALL
       3 = SOUND_OFF
```

### Music Content (0x71)
```
[0]   content type (1-7)
[1]   length (or value for types 8/9/10)
[2+]  content bytes (UTF-8 string)
Content type 8/9/10 = volume control (integer value at byte 2)
```

### Medicine Reminder (0x96)
```
[0]    count
Per medicine:
  [0..3]   start time (epoch/1000, 4 bytes)
  [4..5]   time_1 (hours*3600 | minutes, 2 bytes)
  [6..7]   time_2
  [8..9]   time_3
  [10..11] time_4
  [12]     interval (& 0xFF)
  [13]     repeat flag
  [14]     name length (bytes)
  [15+]    name (UTF-8)
```

### Air Pressure/Altitude (0x95)
```
Formula: pressure = (101.32 - 0.011 * altitude) * 100
[0..1]  pressure (2 bytes)
[2..3]  altitude (2 bytes)
[4..7]  reserved zeros
```

### Menstrual Period Info (0x85)
```
[0]      flag (0x01)
[1..4]   start timestamp (epoch)
[5]      cycle length (days)
[6]      period length (days)
[7]      flag2
[8]      flag3
[9]      flag4
[10]     flag5
[11]     flag6
[12]     flag7
[13]     flag8
... (14 bytes total payload)
```

---

## Device→App Parsing

### Device Info (0x02) — `ProtocolDeviceToApp.b()`
```
[0]  idTotal    (& 0xFF)
[1]  customerId (& 0xFF)
[2]  hardwareId (& 0xFF)
[3]  codeId     (& 0xFF)
[4]  pictureId  (& 0xFF)
[5]  fontId     (& 0xFF)
```

### Alarm List (0x6A) — `ProtocolDeviceToApp.a()`
```
[0]      count
Per alarm (5 bytes each):
  [+0]  id/index
  [+1]  hour
  [+2]  minute
  [+3]  repeat bitmask
  [+4]  enabled flag
```

### Heart Rate History (0x08) — `ProtocolDeviceToApp.c()`
```
[2]      count
Per record (5 bytes each starting at [3]):
  [+0..3] timestamp (DataConvertUtils.c() = 4-byte LE int)
  [+4]    heart rate value
```

### Sport History (0x05) — `ProtocolDeviceToApp.d()`
```
[2]  count
Per record (20 bytes each starting at [3]):
  [+0..3]  timestamp
  [+4..7]  steps
  [+8..11] calories
  [+12..15] distance
  [+16..19] duration
```

### Temperature (0x1A) — `ProtocolDeviceToApp.e(boolean hasSkin)`
```
[2]  count
Per record (6 or 8 bytes depending on hasSkin):
  [+0..3]  timestamp
  [+4..5]  body temperature (2-byte fixed point)
  [+6..7]  skin temperature (if hasSkin=true)
```

---

## OTA Subsystem

Two OTA paths are supported:

1. **ZK OTA** (flag `PREF_KEY_ZK_OTA`): Uses `ZKBleOtaManager` + `ZKBleOtaDataListener`. Communicates via `UUID_WRITE_ZK` (`b003`). OTA data opcode = 0xCA, status = 0xC9.
2. **Bluetrum FOTA** (`com.bluetrum.fota`): Third-party library referenced in `BleConnectService`.

### ZK OTA States
| Value | State |
|-------|-------|
| 1 | `ZK_OTA_READY` |
| 2 | `ZK_OTA_START` |
| 3 | `ZK_OTA_PROGRESS` |
| 4 | `ZK_OTA_STOP` |
| 5 | `ZK_OTA_ALL_FINISH` |
| 6 | `ZK_OTA_PAUSE` |
| 7 | `ZK_OTA_CONTINUE` |
| 8 | `ZK_OTA_ERROR` |
| 9 | `ZK_OTA_VERSION` |

### ZK OTA Error Codes
| Value | Error |
|-------|-------|
| 1 | `ZK_OTA_SAME_FIRMWARE` |
| 2 | `ZK_OTA_KEY_MISMATCH` |
| 11 | `ZK_OTA_CRC_ERROR` |
| 1000 | `ZK_OTA_NOT_CONNECTED` |
| 1001 | `ZK_OTA_NOT_INIT` |
| 1003 | `ZK_OTA_NOT_FOUND_OTA_SERVICE` |
| 1004 | `ZK_OTA_NOT_FOUND_OTA_DATA_IN` |
| 1005 | `ZK_OTA_NOT_FOUND_OTA_DATA_OUT` |
| 1006 | `ZK_OTA_NOT_FOUND_OTA_CHARACTERISTIC` |
| 1007 | `ZK_OTA_NOT_FOUND_CLIENT_CHARACTERISTIC_CONFIG` |
| 1008 | `ZK_OTA_CAN_NOT_SUBSCRIBE_DATA_IN` |
| 1009 | `ZK_OTA_NOT_FOUND_NON_PRIMARY_DEVICE` |
| 1010 | `ZK_OTA_TIMEOUT_SCAN_NON_PRIMARY_DEVICE` |
| 2000 | `ZK_OTA_REPORT_FROM_DEVICE` |
| 2001 | `ZK_OTA_REFUSED_BY_DEVICE` |
| 2002 | `ZK_OTA_TIMEOUT_RECEIVE_RESPONSE` |

---

## BLE Connection State Machine

```
State 0 = IDLE (reset)
State 1 = CONNECTING
State 2 = CONNECTED
State 3 = FAILED / DISCONNECTED (permanent after 5 retries)
State 4 = DISCONNECTING
State 5 = DISCONNECTED (immediate)
```

Reconnect logic: up to **5 automatic reconnect attempts** on GATT error 133 (device too far/lost). After 5 failures → state 3 (failed, no more retries).

Connection timeout: `handler.postDelayed(runnableStopConnect, timeoutMs)` — cleared on descriptor write success.

---

## Same-Screen Mirroring

The `SameScreenBleManager` handles screen mirroring data via dedicated UUIDs:
- Read: `0000b008-0000-1000-8000-00805f9b34fb`
- Write: `0000b009-0000-1000-8000-00805f9b34fb`

Write type is set to `WriteType.WITHOUT_RESPONSE` (value 1).

---

## Platform IDs

The app sends a platform ID (`pid`) in every outgoing packet:

| Value | Platform |
|-------|----------|
| 8 | `UNIVERSAL_PLATFORM` |
| 9 | `ZK_PLATFORM` |
| 255 | `DEFAULT_EXT_PID` |

---

## Broadcast ID Parsing (`ProtocolUtils.b()`)

The BLE advertised manufacturer data is parsed to extract a 4-character hex device ID:
1. Match service UUID `0000e91a-...` in the scan record
2. Manufacturer data must have exactly 1 entry
3. Take first 2 bytes, convert to hex string (padded to 4 chars, uppercase)

The ZK platform is detected by matching service UUID `0000b005-...` in the scan record.
