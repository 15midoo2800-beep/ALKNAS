[app]
title = ALKNAS
package.name = alknas
package.domain = org.alknas
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,csv,db,xlsx
version = 0.1

# تحديد إصدار بايثون المستقر لتجنب بايثون 3.14 التجريبي
requirements = python3==3.11.5,kivy

orientation = portrait
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 21
android.ndk_api = 24

[buildozer]
log_level = 2
warn_on_root = 1
