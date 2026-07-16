# Constants Reference

All hardcoded constants from `com.wtwd.utra.constant.*` and `com.wtwd.utra.entity.*`

---

## Constant.java

```java
// API & Keys
String HOST_API         = "https://wr.watchhealth.com.cn/app-halfwit/"
String AI_KEY           = "rh4s78cdvcw212a76"
String GOOGLE_MAP_KEY   = "AIzaSyDFkGsF5bmlYTEA-oFeatd4MOzZnE7yz8w"
String WEATHER_KEY      = "uqV3vCNsUuPgL7cNZ71AtNcFGVvRXViJ"
String HUAWEI_MAP_KEY   = "DAEDAPlpeYvgTWACx3YzdGFhBmKXS3CPUat3BnGvxIKZAlB3B5u6RdnuDwd6YUeK8YZh7uVS9MYoHIWT89lx+XARE7uNa/zsKVyUEA=="

// BLE
String SERVICE_UUID     = "0000e91a-0000-1000-8000-00805f9b34fb"

// Platform IDs
int UNIVERSAL_PLATFORM  = 8
int ZK_PLATFORM         = 9
int DEFAULT_EXT_PID     = 255

// Chat types
int CHAT_TYPE_BAIDU     = 21
int CHAT_TYPE_GPT       = 22
int CHAT_TYPE_SUCCESS   = 23
int CHAT_TYPE_FAIL      = 24
int CHAT_TYPE_NOT_INITIALIZED = 25

// Audio internal message types
int TYPE_SEND           = 16
int TYPE_RECEIVED       = 17
int AUDIO_DEVICE_START  = 18
int AUDIO_APP_STOP      = 19
int AUDIO_DEVICE_STOP   = 20

// Request codes
int REQUEST_CODE_OPEN_BLUETOOTH     = 1
int REQUEST_CODE_GO_APP_GPS         = 2
int REQUEST_CODE_GO_APP_SETTING     = 3
int REQUEST_CODE_GO_SYSTEM_PHOTO    = 4
int REQUEST_CODE_GO_SYSTEM_CAMERA   = 5
int REQUEST_CODE_GO_SYSTEM_SCREENSHOT = 6

// Global flags
boolean IS_AI_CHAT         = false   // runtime flag
boolean IS_START_BIG_SEND  = false   // dial sync in progress flag
```

---

## BleConstant.java

```java
// BLE UUIDs
String UUID_SERVICE         = "0000e91a-0000-1000-8000-00805f9b34fb"
String UUID_READ            = "0000b001-0000-1000-8000-00805f9b34fb"
String UUID_WRITE           = "0000b002-0000-1000-8000-00805f9b34fb"
String UUID_WRITE_ZK        = "0000b003-0000-1000-8000-00805f9b34fb"
String UUID_ZK              = "0000b005-0000-1000-8000-00805f9b34fb"
String UUID_READ_AUDIO      = "0000b006-0000-1000-8000-00805f9b34fb"
String UUID_READ_SAME_SCREEN  = "0000b008-0000-1000-8000-00805f9b34fb"
String UUID_WRITE_SAME_SCREEN = "0000b009-0000-1000-8000-00805f9b34fb"
String UUID_SYSTEM          = "00002902-0000-1000-8000-00805f9b34fb"  // CCCD
```

---

## SharedPrefsKey.java

```java
// Device
String PREF_KEY_DEVICE_ID       = "PREF_KEY_DEVICE_ID"
String PREF_KEY_DEVICE_MAC      = "PREF_KEY_DEVICE_MAC"
String PREF_KEY_DEVICE_NAME     = "PREF_KEY_DEVICE_NAME"
String PREF_KEY_DEVICE_VERSION  = "PREF_KEY_DEVICE_VERSION"
String PREF_KEY_DEV_TYPE        = "PREF_KEY_DEV_TYPE"
String PREF_KEY_HARDWARE_VERSION= "PREF_KEY_HARDWARE_VERSION"
String PREF_KEY_WATCH_ID        = "PREF_KEY_WATCH_ID"
String PREF_KEY_AUDIO_MAC       = "PREF_KEY_AUDIO_MAC"
String PREF_KEY_FUNCTION_CONTROL= "PREF_KEY_FUNCTION_CONTROL"
String PREF_KEY_ZK_OTA          = "PREF_KEY_ZK_OTA"

// Auth/User
String PREF_KEY_ACCESS_TOKEN    = "PREF_KEY_ACCESS_TOKEN"
String PREF_KEY_REFRESH_TOKEN   = "PREF_KEY_REFRESH_TOKEN"
String PREF_KEY_OVER_TIME       = "PREF_KEY_OVER_TIME"
String PREF_KEY_USER_ID         = "PREF_KEY_USER_ID"
String PREF_KEY_TOURIST_ID      = "PREF_KEY_TOURIST_ID"
String PREF_KEY_ACCOUNT         = "PREF_KEY_ACCOUNT"
String PREF_KEY_PASSWORD        = "PREF_KEY_PASSWORD"       // ⚠️ plaintext
String PREF_KEY_PHONE           = "PREF_KEY_PHONE"
String PREF_KEY_LOGIN_TYPE      = "PREF_KEY_LOGIN_TYPE"

// App state
String PREF_KEY_IS_FIRST        = "PREF_KEY_IS_FIRST"
String PREF_KEY_IS_GUIDE        = "PREF_KEY_IS_GUIDE"
String PREF_KEY_APP_VERSION     = "PREF_KEY_APP_VERSION"
String PREF_KEY_ACTIVE_STATE    = "PREF_KEY_ACTIVE_STATE"
String PREF_KEY_HEAD            = "PREF_KEY_HEAD"           // avatar path
String PREF_KEY_CHAT_TYPE       = "PREF_KEY_CHAT_TYPE"

// Settings
String PREF_KEY_RATE            = "PREF_KEY_RATE"           // BLE MTU rate
String PREF_KEY_SPORT_TYPE      = "PREF_KEY_SPORT_TYPE"
String MUSIC_DEFAULT            = "MUSIC_DEFAULT"           // default music player package
String SPORT_AUTO_PAUSE         = "SPORT_AUTO_PAUSE"
String SPORT_VOICE              = "SPORT_VOICE"
String SCREEN_LIGHT             = "SCREEN_LIGHT"
String BATTERY_POWER            = "BATTERY_POWER"
String WEATHER                  = "WEATHER"
String WEATHER_TIME             = "WEATHER_TIME"
String GPS                      = "GPS"
String LOCATION                 = "LOCATION"
```

---

## HealthEnum.java

```java
// (health-specific enum, minimal contents)
```

---

## DataEnum — All Enums

### EquipmentModel (device type)
```
1 = DEV_WATCH
2 = DEV_VAPE
3 = DEV_SZJ
4 = DEV_TOY
5 = DEV_EYE
6 = DEV_ALARM_CLOCK
7 = DEV_TRANSLATION
8 = DEV_INK
```

### FunctionType (capability bitmask)
```
0x000001 = BLOOD_PRESSURE
0x000002 = BLOOD_OXYGEN
0x000004 = ECG
0x000008 = OLD_WEATHER
0x000010 = NEW_WEATHER
0x000020 = HEART_RATE_24_HOUR
0x000040 = MENSTRUAL_PERIOD
0x000080 = TEMP
0x000100 = MOTOR
0x000200 = ADDRESS_BOOK
0x000400 = BLOOD_SUGAR
0x000800 = SOS
0x001000 = TEMP_SKIN
0x002000 = QR_CODE_PLAY
0x004000 = QR_CODE_FRIEND
0x008000 = GPS_CTRL
0x010000 = HEART_RATE
0x020000 = AI_CODE_CTRL
0x040000 = SAME_SCREEN_CODE_CTRL
0x080000 = OTA_COMPRESS_CTRL
0x100000 = GLU_ALGORITHM
0x200000 = DIAL_COMPRESS_CTRL
0x400000 = HRV
0x800000 = MEDICINE
```

### LanguageType (30 languages)
```
0=ENGLISH, 1=CHINESE, 2=SPAIN, 3=ITALY, 4=PORTUGAL, 5=FRENCH,
6=JAPANESE, 7=RUSSIAN, 8=KOREAN, 9=GERMAN, 10=TRADITIONAL_CHINESE,
11=ARABIC, 12=INDONESIAN, 13=TURKISH, 14=UKRAINIAN, 15=HEBREW,
16=CZECH, 17=GREEK, 18=VIETNAMESE, 19=POLISH, 20=DUTCH,
21=LATIN, 22=ROMANIA, 23=THAI, 24=DANISH, 25=PERSIAN,
26=HUNGARIAN, 27=NEPALI, 28=SWEDEN, 29=INDY
```

### SportType (34 types)
```
0=UNKNOWN, 1=BREATHE, 2=CYCLING, 3=CYCLING_INDOOR, 4=RUNNING_MACHINE,
5=RUN, 6=SWIM, 7=WALK, 8=WEIGHT, 9=YOGA, 10=BADMINTON,
11=BASKETBALL, 12=SKIP, 13=FREE_EXERCISE, 14=FOOTBALL, 15=CLIMBING,
16=PINGPONG, 17=BOWLING, 18=OPENWATER, 19=DANCING, 20=DUMBBELLS,
21=HULOHOOP, 22=STAIRSMOVE, 23=STEPPER, 24=TRIATHLON, 25=SITUPS,
26=SKI, 27=BILLIARDS, 28=ELLIPTICAL_MACHINE, 29=TRAIL_RUNNING,
30=AEROBICS, 31=PILATES, 32=SHUTTLECOCK, 33=SPIN, 34=WALKING_MACHINE
```

### SleepType
```
0=NONE, 1=START, 2=DEEP, 3=LIGHT, 4=WAKE_UP
```

### NoticeType (notification sources)
```
0=NULL, 1=CALL, 2=SMS, 3=QQ, 4=WE_CHAT, 5=MAIL,
6=FACEBOOK, 7=TWITTER, 8=WHATS_APP, 9=INSTAGRAM,
10=SKYPE, 11=LINKED_IN, 12=LINE, 13=OTHER
```

### MusicControlType
```
0=NULL, 1=PLAY, 2=PAUSE, 3=STOP, 4=BACKWARD, 5=FORWARD,
6=PLAY_OR_PAUSE, 7=CONTENT, 8=VOLUME_UP, 9=VOLUME_DOWN, 10=VOLUME_VALUE
```

### WeatherType
```
10=SUNNY_DAY, 11=PARTLY_CLOUDY, 12=CLOUDY_DAY, 13=SHOWER,
14=THUNDERSHOWER, 15=LIGHT_RAIN, 16=MODERATE_RAIN, 17=HEAVY_RAIN,
18=SLEET, 19=LIGHT_SNOW, 20=MODERATE_SNOW, 21=HEAVY_SNOW,
22=SMOG, 23=SANDSTORM
```

### QRCodeType
```
0=NULL, 1=NAME_CARD, 2=PAY_ALIPAY, 3=PAY_WECHAT, 4=PAY_PAYPAL,
5=PAY_GOOGLE, 6=FRIEND_QQ, 7=FRIEND_WECHAT, 8=FRIEND_FACEBOOK,
9=FRIEND_TWITTER, 10=FRIEND_WHATS_APP, 11=FRIEND_INSTAGRAM,
12=OTHER, 13=HEALTH_CODE, 14=NUCLEIN_CODE
```

### SensorType
```
0=NULL, 1=HEART_RATE, 2=BLOOD_PRESSURE, 3=BLOOD_OXYGEN,
4=ECG, 5=TEMPERATURE, 6=BLOOD_SUGAR, 7=HRV
```

### UnitDistanceType
```
0=METER, 16=MILE
```

### UnitWeightType
```
0=KG, 1=POUND, 2=STONE
```

### UnitTempType
```
0=CELSIUS, 1=FAHRENHEIT
```

### RepeatWeek (alarm bitmask)
```
bit 0 (0x01) = SUNDAY
bit 1 (0x02) = MONDAY
bit 2 (0x04) = TUESDAY
bit 3 (0x08) = WEDNESDAY
bit 4 (0x10) = THURSDAY
bit 5 (0x20) = FRIDAY
bit 6 (0x40) = SATURDAY
0x7F = NEVER_REPEAT (one-shot)
0x80 = REPEAT_EVERY_WEEK
0xFF = EVERYDAY
```

### BackgroundType (watch face)
```
0=DEFAULT, 1=SYSTEM, 2=CUSTOMIZE
```

### MenstrualType
```
0=UNKNOWN, 1=NO_PREGNANCY, 2=PREGNANCY
```

### TimeFormat
```
0=TWELVE, 1=TWENTY_FOUR
```

### DateFormat
```
0=MONTH_DAY, 1=DAY_MONTH
```

### BloodSugar Reference (meal timing)
```
1=BREAKFAST_BEFORE, 2=BREAKFAST_AFTER,
3=LUNCH_BEFORE, 4=LUNCH_AFTER,
5=DINNER_BEFORE, 6=DINNER_AFTER,
7=SLEEP_AFTER, 8=WEE_HOURS_AFTER
```

### Temperature conversion (ProtocolUtils)
```java
// Celsius to Fahrenheit:
fahrenheit = celsius * 1.8 + 32

// Distance conversion (unit=16 means miles):
miles = meters * 6.21371192237e-4
km    = meters / 1000
```

### Air Pressure formula
```java
// Altitude (meters) → pressure (hPa * 100):
pressure_raw = (int)((101.32 - 0.011 * altitude) * 100)
// Sent as 2-byte big-endian
```

---

## Database Constants

```java
String DB_NAME = "utra.db"
```

## Notification Service Internals

```java
// Reconnect delay (ms) after BLE disconnection
long RECONNECT_DELAY = ServiceProvider.SCAR_VERSION_FETCH_TIMEOUT
                     // = likely 30000ms (30s)

// Phone state registration
intentFilter.setPriority(Integer.MAX_VALUE)  // highest priority for call intercept

// Minimum data packet length on main notify channel
int MIN_PACKET_LEN = 10
```
