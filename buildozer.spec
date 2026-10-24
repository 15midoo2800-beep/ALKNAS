[app]

# (str) Title of your application
title = Alknas PRO

# (str) Package name
package.name = alknas

# (str) Package domain (needed for android/ios packaging)
package.domain = org.alknas

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,json,dat

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests, bin, .git

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements (النسخة المستقرة والنظيفة لتجنب أخطاء البناء)
requirements = python3,kivy,arabic-reshaper

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) Android application permissions
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,INTERNET

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK will support
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) The Android archs to build for
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) The format used to package the app for debug mode (apk)
android.debug_artifact = apk

# (bool) Enable AndroidX support
android.enable_androidx = True

# (list) packaging options to fix duplicate files
android.add_packaging_options = "exclude 'META-INF/DEPENDENCIES'", "exclude 'META-INF/LICENSE'", "exclude 'META-INF/LICENSE.txt'", "exclude 'META-INF/license.txt'", "exclude 'META-INF/NOTICE'", "exclude 'META-INF/NOTICE.txt'", "exclude 'META-INF/notice.txt'", "exclude 'META-INF/ASL2.0'"

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1
