# Architecture Overview

## Package Structure

```
com.wtwd.utra/
├── api/            # RxJava API base layer (BaseApi, ApiObserver, etc.)
├── ble/            # BLE stack (connect, scan, OTA, audio, same-screen)
├── constant/       # Hardcoded constants, SharedPrefs keys, enums
├── data/           # Data access layer (GreenDAO entities + DAOs)
│   └── greendao/   # Generated DAOs (35 tables)
├── dialog/         # Custom dialog fragments/classes
├── entity/         # Pure data model entities
│   ├── device/     # Device-side entities (alarms, settings, etc.)
│   ├── health/     # Health data entities
│   │   ├── chat/   # Chat messages
│   │   ├── heart/  # Heart rate records
│   │   ├── hrv/    # HRV records
│   │   ├── oxygen/ # Blood oxygen records
│   │   ├── pressure/ # Blood pressure records
│   │   ├── sleep/  # Sleep records
│   │   ├── sport/  # Sport/activity records
│   │   ├── sugar/  # Blood sugar records
│   │   └── temp/   # Temperature records
│   └── user/       # User profile entities
├── eventbus/       # EventBus event POJOs (26 events)
├── jzlib/          # Bundled JZlib (zlib/gzip compression, 23 files)
├── keeplive/       # Android keep-alive mechanisms
│   ├── activity/   # 1-pixel activity trick (OnePixelActivity)
│   ├── config/     # Keep-live notification config
│   ├── receiver/   # Boot/screen-on receivers
│   ├── service/    # Background persistence services
│   └── utils/      # Keep-live utilities
├── manager/        # Singleton managers
├── protocol/       # BLE protocol encoding/decoding
├── receiver/       # Broadcast receivers (phone calls, SMS, notifications)
├── service/        # Android services (GPS, notification listener, etc.)
├── ui/             # All UI layer
│   ├── base/       # Base MVP classes (contracts, models, presenters, views)
│   └── module/     # Feature modules
│       ├── account/    # Auth screens (splash, login, register, etc.)
│       ├── application/ # Application class + global init
│       ├── main/       # Main app screens
│       │   ├── camera/ # Camera/same-screen mirroring feature
│       │   ├── device/ # Device settings (18 sub-sections)
│       │   ├── health/ # Health dashboard (13 sub-sections)
│       │   ├── mine/   # Profile/settings (4 sub-sections)
│       │   └── sport/  # Sport/activity (3 sub-sections)
│       └── qrcode/     # QR code scanner/display
├── utils/          # 47+ utility classes + camera/ + record/ subfolders
└── views/          # Custom views, histograms, recyclers, wheel picker
```

---

## Design Pattern: MVP (Model-View-Presenter)

The app strictly follows MVP:
- **Contract** (`*Contract.java`) — interface defining View and Presenter methods
- **Model** (`*Model.java`) — data access, business logic
- **Presenter** (`*Presenter.java`) — mediates between Model and View
- **Activity/Fragment** — implements View interface

Base classes in `ui/base/`:
- `ToastHelper.java`
- `contract/` — base contract interfaces
- `model/` — base model classes
- `presenter/` — base presenter classes
- `view/` — base view classes

---

## Main Navigation Structure

The app has 4 main tabs (fragments in `MainActivity`):

| Tab | Fragment | Description |
|-----|----------|-------------|
| Home/Dashboard | `MainFragment` or similar | Step count, health summary |
| Health | `HealthFragment` | All health metrics |
| Device | `DeviceFragment` | Watch settings & controls |
| Mine/Profile | `MineFragment` | User profile, app settings |

`MainFragmentPageAdapter` manages the ViewPager.

---

## Account/Auth Flow

```
SplashActivity (entry point, checks login state)
    └── WelcomeActivity (first launch onboarding)
    └── LoginActivity (in account/login/)
    └── RegisterActivity (in account/register/)
    └── PasswordActivity (forgot password, in account/password/)
    └── VerifyActivity (SMS verification, in account/verify/)
    └── CountryActivity (phone country picker, in account/country/)
    └── MainActivity (main app)
```

---

## Device Settings Modules

Under `ui/module/main/device/`:

| Sub-module | Description |
|---|---|
| `alarmclock/` | Alarm clock management |
| `bluetooth/` | BLE device scanning and pairing |
| `bright/` | Screen brightness settings |
| `business/` | Business/enterprise features |
| `contracs/` | Contact management (address book to watch) |
| `editwatch/` | Watch dial/face editing |
| `heart/` | Continuous heart rate monitoring settings |
| `medicine/` | Medicine reminder setup |
| `menstrual/` | Menstrual cycle tracking settings |
| `morewatch/` | Extended watch settings |
| `notice/` | Notification settings (which apps push to watch) |
| `otherset/` | Other settings (DND, sedentary, hand-raise, etc.) |
| `permissions/` | Runtime permission management |
| `picture/` | Watch background picture |
| `sos/` | SOS emergency number |
| `temperature/` | Temperature monitoring settings |
| `update/` | Firmware OTA update |
| `wallet/` | QR code wallet (Alipay/WeChat pay) |

---

## Health Dashboard Modules

Under `ui/module/main/health/`:

| Sub-module | Description |
|---|---|
| `chat/` | AI chat interface |
| `habit/` | Habit tracking |
| `heart/` | Heart rate detail view |
| `hrv/` | HRV (Heart Rate Variability) detail |
| `oxygen/` | Blood oxygen (SpO2) detail |
| `pressure/` | Blood pressure detail |
| `share/` | Health data sharing |
| `sleep/` | Sleep analysis detail |
| `sport/` | Sport history in health context |
| `steps/` | Step count detail |
| `sugar/` | Blood sugar detail |
| `temperature/` | Body temperature detail |
| `wether/` | Weather display (note: typo in code) |

---

## Sport Module

Under `ui/module/main/sport/`:
- `SportFragment` — sport selection
- `AllSportFragment` — list of all sport modes
- `start/` — active sport session tracking
- `details/` — post-sport history details
- `voice/` — sport voice announcements (audio feedback with `AudioIDs`)

---

## Key Singleton Managers

| Class | Role |
|-------|------|
| `BleManager` | BLE singleton (singleton via `LazyHolder`) |
| `DeviceManager` | Current device state (MAC, ID, name) in SharedPrefs |
| `GreenDaoManager` | GreenDAO database singleton, DB name: `utra.db` |
| `UserManager` | Current user info |
| `ActivityManager` | Android activity lifecycle tracking |
| `SubscriptionManager` | RxJava subscription management |

---

## Compression

The app bundles a complete **JZlib** implementation (pure Java, 23 files including `Deflate`, `Inflate`, `InfBlocks`, `InfCodes`, `InfTree`, `GZIPInputStream`, `GZIPOutputStream`).

Used for:
- Compressing dial/watch-face data before BLE transfer (`DATA_TYPE_DIAL_SYNC`, IS_START_BIG_SEND flag)
- OTA firmware compression (`OTA_COMPRESS_CTRL` function bit)

`GZipUtils` utility wraps the JZlib for easy compress/decompress.

---

## Keep-Alive Strategy

The app uses multiple Android keep-alive tricks (in `keeplive/`):
1. **1-pixel Activity** (`OnePixelActivity`) — launched on screen-off to keep process alive
2. **Foreground Service** (`HideForegroundService`) — persistent notification (hidden)
3. **JobScheduler** (`JobHandlerService`) — periodic re-launch
4. **LocalService + RemoteService** pair — dual-process mutual resurrection
5. **Boot receiver** — restarts on device boot (`OnepxReceiver`, `NotificationClickReceiver`)
6. **Screen receivers** — `OnepxReceiver` handles screen on/off
