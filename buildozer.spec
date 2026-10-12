[app]

# (str) Title of your application
title = Alknas

# (str) Package name
package.name = alknas

# (str) Package domain (needed for android packaging)
package.domain = org.alknas.app

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,csv,xlsx,xls,db

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
requirements = python3,kivy,arabic-reshaper,python-bidi,pyjnius,xlrd

# (list) Supported orientations
orientation = portrait

# (list) Permissions (شاملة الكاميرا والموقع الدقيق والاهتزاز والصوت والتخزين)
android.permissions = RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA

# (str) Queries for Android 11+ Package Visibility
android.manifest.queries = <intent><action android:name="android.speech.RecognitionService" /></intent>

# (list) Android architectures to build for (معمارية الهواتف الحديثة 64-bit)
android.archs = arm64-v8a

# (int) Target Android API
android.api = 33

# (int) Minimum API supported
android.minapi = 21

# (str) Android NDK version
android.ndk = 25b

# (str) Android Build-Tools version
android.build_tools_version = 33.0.2

# (bool) Android auto-accept SDK license
android.accept_sdk_license = True

# (bool) Android allow backup
android.allow_backup = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug with command output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
