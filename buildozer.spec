[app]
title = ALKNAS
package.name = alknas
package.domain = org.alknas
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,csv,db,xlsx,ttf
version = 0.3

# إضافة pyjnius للوصول لمحرك أندرويد الصوتي
requirements = python3,kivy,arabic-reshaper,python-bidi,openpyxl,pyjnius

orientation = portrait
# إضافة إذن تسجيل الصوت للميكروفون
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,RECORD_AUDIO
android.archs = arm64-v8a
android.accept_sdk_license = True

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

[buildozer]
log_level = 2
warn_on_root = 1
