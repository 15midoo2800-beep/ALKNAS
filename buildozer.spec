[app]
title = ALKNAS
package.name = alknas
package.domain = org.alknas
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,csv,db,xlsx,ttf
version = 0.7

# المكتبات الأساسية مع تضمين openpyxl و pyjnius
requirements = python3,kivy,arabic-reshaper,python-bidi,openpyxl,pyjnius

orientation = portrait
android.permissions = INTERNET,RECORD_AUDIO,VIBRATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.manifest.application_arguments = android:requestLegacyExternalStorage="true"

android.archs = arm64-v8a
android.accept_sdk_license = True

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

[buildozer]
log_level = 2
warn_on_root = 1
