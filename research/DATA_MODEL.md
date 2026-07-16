# Data Model & Database Schema

The app uses **GreenDAO** ORM with an SQLite database named **`utra.db`**.

Source: `com.wtwd.utra.data.*` and `com.wtwd.utra.data.greendao.*`

---

## Database Tables (35 DAOs found)

| DAO | Table | Key Fields |
|-----|-------|------------|
| `UserInfoDao` | user_info | userId, gender, birthTime, height, weight, wearHand, portrait, name, targetSteps |
| `DeviceSettingDao` | device_setting | deviceId, sosSwitch, sosPhone, tempSwitch, tempTimeInterval, timeFormat, targetRemind, heartAutoSwitch, notDisturbSwitch, notDisturbTime, handRiseSwitch, handRiseTime |
| `AlarmInfoDao` | alarm_info | deviceId, hour, minute, repeatBitmask, enabled |
| `DrinkRemindDao` | drink_remind | deviceId, switch, interval, startTime, endTime |
| `SedentaryRemindDao` | sedentary_remind | deviceId, switch, interval, startTime, endTime |
| `MedicineInfoDao` | medicine_info | deviceId, startTime, time1..4, interval, repeat, name |
| `MenstrualCycleInfoDao` | menstrual_cycle_info | deviceId, startTime, cycleLen, periodLen |
| `MessageNoticeDao` | message_notice | deviceId, callSwitch, smsSwitch, qqSwitch, wechatSwitch, etc. |
| `HeartRateInfoDao` | heart_rate_info | deviceId, date, min, max, avg, resting |
| `HeartRateRecordDao` | heart_rate_record | deviceId, timestamp, heartRate |
| `BloodOxygenInfoDao` | blood_oxygen_info | deviceId, date, min, max, avg |
| `BloodOxygenRecordDao` | blood_oxygen_record | deviceId, timestamp, value |
| `BloodPressureInfoDao` | blood_pressure_info | deviceId, date, systolic, diastolic |
| `BloodPressureRecordDao` | blood_pressure_record | deviceId, timestamp, systolic, diastolic |
| `BloodSugarInfoDao` | blood_sugar_info | deviceId, date, avg, reference |
| `BloodSugarRecordDao` | blood_sugar_record | deviceId, timestamp, value, mealType |
| `BloodSugarReferenceDao` | blood_sugar_reference | reference type, thresholds |
| `BloodSugarStandardDao` | blood_sugar_standard | standard normal ranges |
| `SleepInfoDao` | sleep_info | deviceId, date, total, deep, light, rem, wakeCount |
| `SleepRecordDao` | sleep_record | deviceId, timestamp, type (deep/light/wake/rem) |
| `HRVInfoDao` | hrv_info | deviceId, date, value, rmssd, sdnn |
| `HRVRecordDao` | hrv_record | deviceId, timestamp, value |
| `TempInfoDao` | temp_info | deviceId, date, bodyTemp, skinTemp, avg |
| `TempRecordDao` | temp_record | deviceId, timestamp, bodyTemp, skinTemp |
| `SportRecordDao` | sport_record | deviceId, startTime, endTime, type, steps, calories, distance, duration |
| `SportModeInfoDao` | sport_mode_info | deviceId, sportType, enabled, goalType, goalValue |
| `SportDetailsDao` | sport_details | sportRecordId, timestamp, heartRate, pace, etc. |
| `SportSettingDao` | sport_setting | deviceId, autoPause |
| `TargetInfoDao` | target_info | deviceId, steps, calories, distance, sleep |
| `UnitSettingDao` | unit_setting | deviceId, distance (metric/imperial), weight (kg/lb/stone), temp (C/F) |
| `DialInfoDao` | dial_info | deviceId, dialId, preview, category, etc. |
| `ChatMessageInfoDao` | chat_message_info | deviceId, timestamp, content, role (user/ai), type |
| `AppVersionInfoDao` | app_version_info | versionCode, versionName, updateUrl, forceUpdate |

---

## Entity Details

### UserInfo
```java
long   userId
String gender      // JSON key: "sex"
String age         // JSON key: "birthTime" (birth date string)
String height      // cm
String weight      // kg
int    wearHand    // 0=left, 1=right
String headPath    // JSON key: "portrait" (avatar URL)
String name
String targetSteps
```

### DeviceSetting
```java
long   deviceId
int    sosSwitch          // 0=off, 1=on
String sosPhone           // emergency number
int    tempSwitch         // body temp monitoring
int    tempTimeInterval   // monitoring interval enum (TimeIntervalType)
int    timeFormat         // 0=12h, 1=24h
int    targetRemind       // 0=off, 1=on
int    heartAutoSwitch    // 24h heart rate monitoring
int    notDisturbSwitch   // Do Not Disturb
String notDisturbTime     // format "HH:mm-HH:mm"
int    handRiseSwitch     // raise-to-wake
String handRiseTime       // format "HH:mm-HH:mm"
```

### AlarmInfo (device entity)
```java
// BLE wire format: [id][hour][minute][repeatBitmask][enabled]
int id
int hour
int minute
int repeatBitmask   // see RepeatWeek bitmask
int enabled
```

### HeartRateInfo (health entity)
```java
long   deviceId
String date        // yyyy-MM-dd
int    min
int    max
int    avg
int    resting
```

### HeartRateRecord (health entity)
```java
long deviceId
long timestamp    // epoch ms
int  heartRate
```

### SleepRecord
```java
long deviceId
long timestamp
int  sleepType  // 0=NONE, 1=START, 2=DEEP, 3=LIGHT, 4=WAKE_UP
```

### SportRecord
```java
long   deviceId
long   startTime
long   endTime
int    sportType     // see SportType enum (34 sport types)
int    steps
int    calories
float  distance      // meters
int    duration      // seconds
int    avgHeartRate
```

### SportModeInfo
```java
long deviceId
int  sportType
int  enabled
int  goalType    // steps/calories/distance/time
long goalValue
```

### MedicineInfo (device entity)
```java
long   deviceId
long   startTime  // ms timestamp
int    time1..4   // reminder times in seconds from midnight
int    interval   // days between reminders
int    repeat     // repeat enabled
String name       // medicine name (UTF-8, max ~48 bytes)
```

### MenstrualCycleInfo
```java
long deviceId
long startTime   // period start timestamp
int  cycleLength // days
int  periodLength // days
```

### ChatMessageInfo
```java
long   deviceId
long   timestamp
String content   // message text
int    role      // user or AI
int    chatType  // BAIDU or GPT
```

### DeviceInfo (device hardware info)
```java
int idTotal      // total ID count on device
int customerId   // customer/brand ID
int hardwareId   // hardware revision
int codeId       // firmware code ID
int pictureId    // current dial picture ID
int fontId       // font pack ID
```

### DialInfo
```java
long   deviceId
String dialId
String previewUrl
String category
int    isDefault
```

---

## Data Access Pattern

```java
// Singleton access
GreenDaoManager.c().b()  // → DaoSession

// Example query
DaoSession daoSession = GreenDaoManager.c().b();
HeartRateInfoDao dao = daoSession.getHeartRateInfoDao(); // etc.
```

The `DaoSession` exposes named getter methods (`.w()`, `.x()`, etc.) for each DAO — the method names are obfuscated single letters.

---

## Health Data Aggregation Classes

These classes (in `com.wtwd.utra.data/`) perform daily/weekly/monthly aggregation with chart-ready output:

| Class | Aggregates |
|-------|-----------|
| `HeartRateData` | Min/max/avg heart rate by day/week/month |
| `BloodOxygenData` | SpO2 averages and trends |
| `BloodPressureData` | Systolic/diastolic trends |
| `BloodSugarData` | Blood glucose by meal reference |
| `BloodSugarReferenceData` | Reference range calculations |
| `SleepData` | Deep/light/REM/wake breakdown |
| `SportData` | Multi-sport session aggregation |
| `HRVData` | HRV trend and RMSSD calculations |
| `TempData` | Body + skin temperature trends |

---

## Database Migration

`MigrationHelper.java` and `MyOpenHelper.java` handle schema upgrades.
The DB version is tracked in `DaoMaster`.

---

## Histogram/Chart Views

Custom canvas-drawn histogram views for each health metric (in `views/histogram/`):

| View | Data |
|------|------|
| `HeartRateHistogramView` | Heart rate over time |
| `BloodOxygenHistogramView` | SpO2 over time |
| `BloodPressureHistogramView` | Systolic/diastolic bars |
| `BloodSugarHistogramView` | Glucose with meal markers |
| `HRVHistogramView` | HRV with RMSSD/SDNN annotations |
| `SleepHistogramView` | Sleep stage stacked bars |
| `SportHistogramView` | Multi-sport activity bars |
| `StepHistogramView` | Daily step count bars |
| `TempHistogramView` | Body + skin temperature overlay |
| `HistogramView` | Generic base histogram |
| `HistogramBgView` | Background grid/axis drawing |
