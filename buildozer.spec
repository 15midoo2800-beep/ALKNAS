[app]
title = ALKNAS
package.name = alknas
package.domain = org.alknas
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,csv,db,xlsx
version = 0.1

# كتابة python3 بدون رقم إصدار
requirements = python3,kivy

orientation = portrait
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True

# تثبيت إصدارات الـ API و NDK المستقرة المتوافقة مع Kivy
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

[buildozer]
log_level = 2
warn_on_root = 1
