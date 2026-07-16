# EventBus Events

All events in `com.wtwd.utra.eventbus.*`. The app uses **GreenRobot EventBus** (`ya.b`) for inter-component communication (26 events found).

---

## Complete Event List

### Bluetooth Events

#### `BluetoothSwitchStateEvent`
Fired when Android Bluetooth adapter state changes.
```java
int state:
  0 = TURNING_ON (BT adapter state 11)
  1 = ON (adapter state 12)
  2 = TURNING_OFF (adapter state 13)
  3 = OFF (adapter state 10)
```

#### `BluetoothScanStateEvent`
Fired by `BleManager.d()` when scan state changes.
```java
int state:
  0 = SCAN_STARTED
  1 = SCAN_COMPLETE
```

#### `BluetoothScanDeviceEvent`
Fired when a BLE device is found during scan.
```java
// Three constructors:
BluetoothDevice device, int rssi, byte[] scanRecord   // legacy scan
int callbackType, ScanResult scanResult               // Android 5+ scan
List<ScanResult> results                              // batch results
```

#### `BluetoothConnectStateEvent`
Fired by `BleManager.b()` for GATT connection state changes.
```java
BluetoothDevice device
int state:
  1 = CONNECTING
  2 = CONNECTED
  3 = FAILED
  4 = DISCONNECTING
  5 = DISCONNECTED
```

#### `BluetoothBondStateEvent`
Fired on Bluetooth bonding state changes.
```java
BluetoothDevice device
int bondState:   // Android standard bond states
  10 = BOND_NONE (unpaired)
  11 = BOND_BONDING
  12 = BOND_BONDED
```

#### `BluetoothReadDataEvent`
Fired when data is received on main notify characteristic (`UUID_READ` = `b001`).
```java
BluetoothDevice device
byte[] data    // raw BLE packet bytes
```

#### `BluetoothReadAudioDataEvent`
Fired when audio data is received on audio notify characteristic (`UUID_READ_AUDIO` = `b006`).
```java
byte[] data    // PCM/Opus audio frame bytes
```

#### `BluetoothReadSameScreenDataEvent`
Fired when screen-mirroring data arrives on `UUID_READ_SAME_SCREEN` (`b008`).
```java
byte[] data    // screen frame data
```

#### `BluetoothReadSameScreenPictureDataEvent`
A separate event for full picture (vs streaming frame) same-screen data.
```java
byte[] data
```

#### `BluetoothAudioStateDataEvent`
Fired when the device reports its audio connection state (opcode `0x34`).
```java
// audio state data from device
```

---

### Device Events

#### `DeviceInfoEvent`
Fired when device hardware info is received (opcode `0x02`).
```java
DeviceInfo deviceInfo  // idTotal, customerId, hardwareId, codeId, pictureId, fontId
```

#### `DeviceSettingEvent`
Fired when device settings are updated/received.

#### `DeviceTypeEvent`
Fired when device type packet (`0x33`) is received.
```java
int deviceType:
  1 = DEV_WATCH
  2 = DEV_VAPE
  3 = DEV_SZJ
  4 = DEV_TOY
  5 = DEV_EYE
  6 = DEV_ALARM_CLOCK
  7 = DEV_TRANSLATION
  8 = DEV_INK
```

#### `DeviceAnswerEvent`
Fired when device sends an acknowledgment/answer packet.
```java
int answerType:
  0 = NULL
  1 = SUCCESS
  2 = WRONG
  3 = CRC16_WRONG
  4 = OVER
```

#### `BatteryElectricityEvent`
Fired when battery level packet (opcode `0x03`) is received.
```java
int batteryLevel   // 0-100
```

#### `FunctionControlEvent`
Fired when function capability bitmask is received/updated.
```java
int functionControl   // bitmask, see FunctionType enum
```

---

### Health Data Events

#### `HealthDataEvent`
Multi-purpose health data event. Contains typed data based on the data type opcode.
```java
int dataType      // matches ProtocolEnum.DataType values
Object data       // type-specific health object (HeartRateInfo, SleepRecord, etc.)
```

#### `SportStateEvent`
Fired when real-time sport state changes.
```java
int sportState:
  0 = STOP
  1 = START
  2 = PAUSE
  3 = CONTINUE
  4 = STOP_FORCE
  5 = SYNC
```

#### `SportHeartRateEvent`
Fired with real-time heart rate during exercise (opcode `0x11`).
```java
int heartRate
```

#### `SensorDataControlEvent`
Fired when sensor monitoring mode changes.
```java
int sensorType:
  0 = NULL
  1 = HEART_RATE
  2 = BLOOD_PRESSURE
  3 = BLOOD_OXYGEN
  4 = ECG
  5 = TEMPERATURE
  6 = BLOOD_SUGAR
  7 = HRV
int state   // open or close
```

---

### Notification/Reminder Events

#### `AlarmInfoEvent`
Fired when alarm clock data is received/updated from device.

#### `MedIcineEvent` (note: typo in code)
Fired when medicine reminder event occurs.

#### `DeviceSettingEvent`
General device setting sync notification.

---

### UI/Control Events

#### `PhotographStateEvent`
Fired when watch triggers camera shutter (opcode `0x74`).
```java
int state   // photograph trigger state
```

#### `AIConnectStateEvent`
Fired when AI assistant connection state changes.
```java
int state:
  21 = CHAT_TYPE_BAIDU
  22 = CHAT_TYPE_GPT
  23 = CHAT_TYPE_SUCCESS
  24 = CHAT_TYPE_FAIL
  25 = CHAT_TYPE_NOT_INITIALIZED
```

#### `ChatDisplayDataEvent`
Fired when AI chat response is ready for display.
```java
// chat response data
```

---

### OTA Events

#### `ZKBluetoothOtaDataEvent`
Fired for all ZK OTA firmware update state transitions.
```java
int state:      // matches ZKOtaState values (1-9)
Object data:    // progress int (for PROGRESS state) or error string (for ERROR state)
```

---

## Event Bus Usage Pattern

```java
// Subscribe (in Activity/Fragment/Service):
@Subscribe(threadMode = ThreadMode.MAIN)
public void onBluetoothConnectState(BluetoothConnectStateEvent event) { ... }

// Post:
EventBus.getDefault().post(new BluetoothConnectStateEvent(device, state));
// (obfuscated as: b.b().f(new BluetoothConnectStateEvent(...)))
```

The audio read events use **RxBus** (custom RxJava bus in `utils/RxBus.java`) instead of EventBus, due to the high frequency of audio data callbacks.
