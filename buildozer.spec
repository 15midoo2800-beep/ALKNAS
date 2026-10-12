[app]
title = Alknas
package.name = alknas
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,csv,xlsx,xls,db

# المتطلبات شاملة دعم إكسيل والنصوص العربية وميزات النظام
requirements = python3,kivy,arabic-reshaper,python-bidi,pyjnius,openpyxl,xlrd,et_xmlfile

# الصلاحيات المطلوبة للميكروفون والذاكرة والاهتزاز
android.permissions = RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE

# استعلام خدمات النظام الصوتي لأندرويد 11 فما فوق
android.manifest.queries = <intent><action android:name="android.speech.RecognitionService" /></intent>

# المعماريات المستهدفة لهواتف أندرويد الحديثة
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
