[app]

# (str) Title of your application
title = Alknas

# (str) Package name
package.name = alknas

# (str) Package domain (needed for android packaging)
package.domain = org.test

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,csv,xlsx,xls,db

# (str) Application versioning (السطر الذي كان مفقوداً وسبب الخطأ)
version = 0.1

# (list) Application requirements
requirements = python3,kivy,arabic-reshaper,python-bidi,pyjnius,openpyxl,xlrd,et_xmlfile

# (list) Permissions
android.permissions = RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE

# (str) Android queries for Android 11+
android.manifest.queries = <intent><action android:name="android.speech.RecognitionService" /></intent>

# (list) Supported orientations
orientation = portrait

# (list) Android architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) Android allow backup
android.allow_backup = True
