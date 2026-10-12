import os
import csv
import re
import sqlite3
import hashlib
import hmac
import threading
import urllib.parse
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.utils import platform

import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = "font.ttf" if os.path.exists("font.ttf") else "Roboto"
MASTER_SECRET = b"ALKNAS_TACTICAL_MILITARY_KEY_2026_SECURE"

def ar(text):
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

EASTERN_TO_WESTERN = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

def clean_input(text):
    if not text:
        return "", ""
    t = str(text).translate(EASTERN_TO_WESTERN).strip()
    digits = "".join(re.findall(r'\d+', t))
    letters = "".join(re.findall(r'[\u0600-\u06FFa-zA-Z]+', t))
    return digits, letters

class SecurityVault:
    """وحدة الأمان وفحص الترخيص والعتاد"""
    @staticmethod
    def get_device_id():
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                SettingsSecure = autoclass('android.provider.Settings$Secure')
                contentResolver = PythonActivity.mActivity.getContentResolver()
                dev_id = SettingsSecure.getString(contentResolver, SettingsSecure.ANDROID_ID)
                if dev_id:
                    return hashlib.md5(dev_id.encode('utf-8')).hexdigest()[:12].upper()
            except Exception:
                pass
        return "DEV-DEMO-TEST1"

    @staticmethod
    def verify_key(device_id, key_str):
        try:
            parts = key_str.strip().split("-")
            if len(parts) != 3 or parts[0] != "ALK":
                return False, "تنسيق المفتاح غير صحيح"
            expiry_str = parts[1]
            provided_sig = parts[2].upper()

            payload = f"{device_id}:{expiry_str}".encode('utf-8')
            expected_sig = hmac.new(MASTER_SECRET, payload, hashlib.sha256).hexdigest()[:12].upper()

            if not hmac.compare_digest(provided_sig, expected_sig):
                return False, "مفتاح التفعيل لا يتطابق مع هذا الجهاز"

            now_int = int(datetime.now().strftime("%Y%m%d"))
            exp_int = int(expiry_str)
            if now_int > exp_int:
                return False, "انتهت صلاحية هذا الترخيص"

            return True, f"مرخص حتى: {expiry_str}"
        except Exception:
            return False, "فشل التحقق من صحة الترخيص"

class AlknasApp(App):
    def build(self):
        self.tts = None
        self.current_target = None
        self.saved_whatsapp_number = "966500000000"
        self.pending_photo_path = None
        self.pending_report_text = ""
        self.is_licensed = False

        if platform == 'android':
            self.db_name = os.path.join(self.user_data_dir, "plates_vault.db")
        else:
            self.db_name = "plates_vault.db"

        self.root_box = BoxLayout(orientation='vertical', padding=12, spacing=8)

        # 1. شريط العنوان والترخيص
        header = BoxLayout(orientation='horizontal', size_hint=(1, 0.08))
        self.lbl_targets = Label(
            text=ar("الأهداف: 0 | جاري التحقق"),
            font_name=FONT_PATH,
            font_size='12sp',
            color=(0.2, 1.0, 0.5, 1),
            size_hint=(0.55, 1)
        )
        header.add_widget(self.lbl_targets)

        self.lbl_title = Label(
            text=ar("القناص PRO 🎯"),
            font_name=FONT_PATH,
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.45, 1)
        )
        header.add_widget(self.lbl_title)
        self.root_box.add_widget(header)

        # 2. أزرار التحكم
        ctrl_bar = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.08))
        self.btn_history = Button(
            text=ar("📋 سجل الأهداف"),
            font_name=FONT_PATH,
            font_size='13sp',
            background_color=(0.15, 0.2, 0.3, 1)
        )
        self.btn_history.bind(on_press=self.show_hit_history)
        ctrl_bar.add_widget(self.btn_history)

        self.btn_import = Button(
            text=ar("📁 استيراد مشفر (Excel/CSV)"),
            font_name=FONT_PATH,
            font_size='13sp',
            background_color=(0.1, 0.35, 0.25, 1)
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        ctrl_bar.add_widget(self.btn_import)
        self.root_box.add_widget(ctrl_bar)

        # 3. إطار لوحة السيارة
        self.input_plate = TextInput(
            hint_text=ar("أدخل اللوحة (مثال: 1955 ح هـ ن)"),
            font_name=FONT_PATH,
            multiline=False,
            font_size='22sp',
            halign='center',
            size_hint=(1, 0.11),
            background_color=(0.95, 0.95, 0.98, 1),
            foreground_color=(0.05, 0.05, 0.05, 1),
            padding=[8, 12]
        )
        self.root_box.add_widget(self.input_plate)

        # 4. أزرار الفحص المتعددة (صوت + فحص يدوي)
        action_bar = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.1))
        self.btn_voice = Button(
            text=ar("🎙️ فحص صوتي"),
            font_name=FONT_PATH,
            font_size='15sp',
            bold=True,
            background_color=(0.85, 0.15, 0.2, 1)
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_bar.add_widget(self.btn_voice)

        self.btn_search = Button(
            text=ar("🔍 فحص اللوحة"),
            font_name=FONT_PATH,
            font_size='15sp',
            bold=True,
            background_color=(0.1, 0.45, 0.85, 1)
        )
        self.btn_search.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        action_bar.add_widget(self.btn_search)
        self.root_box.add_widget(action_bar)

        # 5. شاشة الرادار المركزية
        self.result_panel = Label(
            text=ar("المنظومة التكتيكية مؤمنة ونشطة.\nأدخل اللوحة أو استخدم الصوت للبحث."),
            font_name=FONT_PATH,
            font_size='15sp',
            halign='center',
            valign='middle',
            color=(0.8, 0.85, 0.9, 1),
            size_hint=(1, 0.53)
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        self.root_box.add_widget(self.result_panel)

        # 6. زر إرسال واتساب الميداني
        self.btn_whatsapp = Button(
            text=ar("🚀 إرسال الموقع والتوثيق للواتساب"),
            font_name=FONT_PATH,
            font_size='14sp',
            bold=True,
            background_color=(0.1, 0.7, 0.3, 1),
            size_hint=(1, 0.1)
        )
        self.btn_whatsapp.bind(on_press=self.open_whatsapp_dialog)
        self.btn_whatsapp.opacity = 0
        self.btn_whatsapp.disabled = True
        self.root_box.add_widget(self.btn_whatsapp)

        Clock.schedule_once(self._startup_check, 0.4)
        return self.root_box

    def _startup_check(self, dt):
        """فحص الأمان والترخيص ومنع التلاعب بالتاريخ"""
        self.init_database()
        dev_id = SecurityVault.get_device_id()

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT value FROM config WHERE key="license_key"')
        row_lic = c.fetchone()
        c.execute('SELECT value FROM config WHERE key="last_sync_time"')
        row_sync = c.fetchone()

        now_int = int(datetime.now().strftime("%Y%m%d%H%M"))
        last_sync = int(row_sync[0]) if row_sync else 0

        # فحص إرجاع تاريخ الهاتف
        if now_int < last_sync:
            conn.close()
            self._lockout_tamper()
            return

        c.execute('INSERT OR REPLACE INTO config (key, value) VALUES ("last_sync_time", ?)', (str(now_int),))
        conn.commit()

        license_key = row_lic[0] if row_lic else ""
        valid, msg = SecurityVault.verify_key(dev_id, license_key)
        conn.close()

        if valid:
            self.is_licensed = True
            self.lbl_targets.text = ar(f"الأهداف: {self.get_total_records()} | {msg}")
            self._init_android_safe()
        else:
            self.show_activation_dialog(dev_id, msg)

    def _lockout_tamper(self):
        """قفل التطبيق عند كشف تلاعب بالوقت"""
        box = BoxLayout(orientation='vertical', padding=14, spacing=10)
        lbl = Label(text=ar("⚠️ تنبيه أمني:\nتم اكتشاف تلاعب في وقت النظام!\nتم تعليق التطبيق لحماية البيانات."),
                    font_name=FONT_PATH, font_size='14sp', halign='center', color=(1, 0.2, 0.2, 1))
        lbl.bind(size=lbl.setter('text_size'))
        box.add_widget(lbl)
        pop = Popup(title=ar("حظر أمني"), title_font=FONT_PATH, content=box, size_hint=(0.9, 0.5), auto_dismiss=False)
        pop.open()

    def show_activation_dialog(self, dev_id, reason=""):
        """نافذة طلب التفعيل للعميل"""
        box = BoxLayout(orientation='vertical', padding=12, spacing=8)
        box.add_widget(Label(text=ar("نسخة تجارية مقفلة - مطلوب التفعيل"), font_name=FONT_PATH, font_size='14sp', bold=True))
        box.add_widget(Label(text=ar(f"كود جهازك (أرسله للإدارة):\n{dev_id}"), font_name=FONT_PATH, font_size='13sp', color=(0.4, 0.8, 1, 1)))

        inp_key = TextInput(hint_text=ar("الصق مفتاح التفعيل هنا (ALK-...)"), font_name=FONT_PATH, multiline=False, size_hint=(1, 0.2), halign='center')
        box.add_widget(inp_key)

        lbl_status = Label(text=ar(reason), font_name=FONT_PATH, font_size='12sp', color=(1, 0.4, 0.4, 1))
        box.add_widget(lbl_status)

        btn_act = Button(text=ar("تفعيل الترخيص"), font_name=FONT_PATH, size_hint=(1, 0.22), background_color=(0.1, 0.7, 0.3, 1))
        box.add_widget(btn_act)

        pop = Popup(title=ar("تفعيل القناص"), title_font=FONT_PATH, content=box, size_hint=(0.92, 0.65), auto_dismiss=False)

        def do_activate(x):
            key = inp_key.text.strip()
            ok, msg = SecurityVault.verify_key(dev_id, key)
            if ok:
                conn = sqlite3.connect(self.db_name)
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO config (key, value) VALUES ("license_key", ?)', (key,))
                conn.commit()
                conn.close()
                self.is_licensed = True
                pop.dismiss()
                self.lbl_targets.text = ar(f"الأهداف: {self.get_total_records()} | {msg}")
                self._init_android_safe()
            else:
                lbl_status.text = ar(msg)

        btn_act.bind(on_press=do_activate)
        pop.open()

    def _init_android_safe(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.RECORD_AUDIO,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.VIBRATE,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                    Permission.CAMERA
                ])
                from jnius import autoclass
                from android import activity
                activity.bind(on_activity_result=self.on_activity_callback)

                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                self.tts = TextToSpeech(PythonActivity.mActivity, None)
            except Exception as e:
                print("Android init error:", e)

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_clean TEXT,
                digits_only TEXT,
                letters_only TEXT,
                plate_original TEXT,
                chassis_number TEXT,
                bank_name TEXT,
                car_model TEXT
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_plate_clean ON vehicles(plate_clean)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_digits ON vehicles(digits_only)')
        c.execute('''
            CREATE TABLE IF NOT EXISTS hits_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT,
                bank TEXT,
                model TEXT,
                chassis TEXT,
                created_at TEXT
            )
        ''')
        c.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('SELECT value FROM config WHERE key="wa_number"')
        row = c.fetchone()
        if row:
            self.saved_whatsapp_number = row[0]
        else:
            c.execute('INSERT INTO config VALUES ("wa_number", "966500000000")')
        conn.commit()
        conn.close()

    def get_total_records(self):
        try:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM vehicles')
            cnt = c.fetchone()[0]
            conn.close()
            return f"{cnt:,}"
        except Exception:
            return "0"

    def get_precise_location(self):
        if platform != 'android':
            return 24.7136, 46.6753
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            activity = PythonActivity.mActivity
            loc_service = activity.getSystemService(Context.LOCATION_SERVICE)

            best = None
            for p in ['gps', 'network', 'passive']:
                try:
                    if loc_service.isProviderEnabled(p):
                        loc = loc_service.getLastKnownLocation(p)
                        if loc and (best is None or loc.getTime() > best.getTime()):
                            best = loc
                except Exception:
                    continue
            if best:
                return best.getLatitude(), best.getLongitude()
        except Exception as e:
            print("Location error:", e)
        return None, None

    def search_plate(self, query):
        if not self.is_licensed:
            self.result_panel.text = ar("التطبيق غير مفعل! يرجى إدخال كود الترخيص.")
            return

        digits_q, letters_q = clean_input(query)
        if not digits_q and not letters_q:
            self.result_panel.text = ar("يرجى إدخال أو نطق رقم اللوحة أولاً!")
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        row = None

        if digits_q and letters_q:
            c.execute('''
                SELECT plate_original, chassis_number, bank_name, car_model 
                FROM vehicles 
                WHERE digits_only = ? AND (letters_only = ? OR letters_only LIKE ?)
                LIMIT 1
            ''', (digits_q, letters_q, f"%{letters_q}%"))
            row = c.fetchone()

        if not row and digits_q:
            c.execute('SELECT plate_original, chassis_number, bank_name, car_model FROM vehicles WHERE digits_only = ? LIMIT 1', (digits_q,))
            row = c.fetchone()

        if row:
            plate, chassis, bank, model = row
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('INSERT INTO hits_log (plate, bank, model, chassis, created_at) VALUES (?, ?, ?, ?, ?)', (plate, bank, model, chassis, now_str))
            conn.commit()
            conn.close()

            self.current_target = {"plate": plate, "model": model, "chassis": chassis, "bank": bank, "time": now_str}
            res = (
                f"🚨 تم رصد هدف مطلوب! 🚨\n\n"
                f"اللوحة: {plate}\n"
                f"الموديل: {model}\n"
                f"الشاص: {chassis}\n"
                f"الجهة: {bank}"
            )
            self.result_panel.text = ar(res)
            self.result_panel.color = (0.2, 1.0, 0.5, 1)

            self.btn_whatsapp.opacity = 1
            self.btn_whatsapp.disabled = False

            if platform == 'android':
                try:
                    from jnius import autoclass
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    Context = autoclass('android.content.Context')
                    vib = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
                    vib.vibrate([0, 400, 200, 400], -1)
                except Exception:
                    pass
        else:
            conn.close()
            self.current_target = None
            self.result_panel.text = ar(f"اللوحة ({query})\nليست مسجلة ضمن الأهداف.")
            self.result_panel.color = (0.85, 0.4, 0.4, 1)
            self.btn_whatsapp.opacity = 0
            self.btn_whatsapp.disabled = True

    def start_voice_recognition(self, instance):
        if not self.is_licensed:
            self.result_panel.text = ar("التطبيق غير مفعل!")
            return
        if platform != 'android':
            self.result_panel.text = ar("البحث الصوتي متاح على الأندرويد.")
            return

        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar-EG")
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "انطق رقم وحروف اللوحة...")

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 1001)
        except Exception:
            self.result_panel.text = ar("تعذر فتح الميكروفون.")

    def open_system_file_picker(self, instance):
        if not self.is_licensed:
            self.result_panel.text = ar("التطبيق غير مفعل!")
            return
        if platform != 'android':
            self.result_panel.text = ar("اختيار الملفات متاح على الهاتف.")
            return

        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')

            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("*/*")
            intent.addCategory(Intent.CATEGORY_OPENABLE)

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 2002)
        except Exception as e:
            self.result_panel.text = ar(f"خطأ في فتح الملف: {e}")

    def capture_car_photo(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pending_photo_path = os.path.join(self.user_data_dir, f"car_{timestamp}.jpg")

        if platform == 'android':
            try:
                from jnius import autoclass, cast
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                File = autoclass('java.io.File')
                Uri = autoclass('android.net.Uri')

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                photo_file = File(self.pending_photo_path)
                file_uri = Uri.fromFile(photo_file)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, file_uri)

                currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
                currentActivity.startActivityForResult(intent, 3003)
                return
            except Exception as e:
                print("Camera error:", e)

        self._dispatch_to_whatsapp(self.saved_whatsapp_number, self.pending_report_text, None)

    def on_activity_callback(self, request_code, result_code, data):
        try:
            if request_code == 1001:
                from jnius import autoclass
                Activity = autoclass('android.app.Activity')
                if result_code != Activity.RESULT_OK or data is None:
                    self.result_panel.text = ar("تم إلغاء الصوت أو لم يتم التقاطه.")
                    return
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    val = str(results.get(0)).strip()
                    self.input_plate.text = val
                    self.search_plate(val)

            elif request_code == 2002 and data is not None:
                uri = data.getData()
                if uri is not None:
                    self.result_panel.text = ar("جاري معالجة وتشفير الملف المرفوع...")
                    threading.Thread(target=self._copy_and_read, args=(uri,), daemon=True).start()

            elif request_code == 3003:
                photo_to_send = self.pending_photo_path if (self.pending_photo_path and os.path.exists(self.pending_photo_path)) else None
                self._dispatch_to_whatsapp(self.saved_whatsapp_number, self.pending_report_text, photo_to_send)
        except Exception as e:
            print("Activity error:", e)

    def _copy_and_read(self, uri):
        pfd = None
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            contentResolver = activity.getContentResolver()

            pfd = contentResolver.openFileDescriptor(uri, "r")
            fd = pfd.getFd()

            temp_path = os.path.join(self.user_data_dir, "temp_data_file")
            with open(fd, "rb", closefd=False) as src, open(temp_path, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
            pfd.close()

            self._import_worker(temp_path)
        except Exception as e:
            if pfd:
                try: pfd.close()
                except Exception: pass
            Clock.schedule_once(lambda dt: self._done_import(0, str(e)), 0)

    def _import_worker(self, file_path):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('PRAGMA synchronous = OFF')
        c.execute('PRAGMA journal_mode = MEMORY')
        c.execute('DELETE FROM vehicles')

        count = 0
        batch = []
        try:
            with open(file_path, mode='r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and str(row[0]).strip():
                        r0 = str(row[0]).strip()
                        digits, letters = clean_input(r0)
                        clean = digits + letters
                        other_cols = [str(col).strip() for col in row[1:4]]
                        while len(other_cols) < 3:
                            other_cols.append("")
                        chassis = other_cols[1]
                        bank = other_cols[2]
                        model = other_cols[0]

                        batch.append((clean, digits, letters, r0, chassis, bank, model))
                        count += 1
                        if len(batch) >= 5000:
                            c.executemany('INSERT INTO vehicles (plate_clean, digits_only, letters_only, plate_original, chassis_number, bank_name, car_model) VALUES (?, ?, ?, ?, ?, ?, ?)', batch)
                            batch.clear()

            if batch:
                c.executemany('INSERT INTO vehicles (plate_clean, digits_only, letters_only, plate_original, chassis_number, bank_name, car_model) VALUES (?, ?, ?, ?, ?, ?, ?)', batch)

            conn.commit()
            conn.close()
            Clock.schedule_once(lambda dt: self._done_import(count, None), 0)
        except Exception as e:
            conn.close()
            Clock.schedule_once(lambda dt: self._done_import(0, str(e)), 0)

    def _done_import(self, cnt, err):
        if err:
            self.result_panel.text = ar(f"تنبيه الاستيراد:\n{err}")
        else:
            self.result_panel.text = ar(f"اكتمل الاستيراد بنجاح!\nتم تشفير وتخزين {cnt:,} سيارة.")
            self.lbl_targets.text = ar(f"الأهداف: {self.get_total_records()} | نشط")

    def open_whatsapp_dialog(self, instance):
        if not self.current_target:
            return

        box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        box.add_widget(Label(text=ar("رقم الواتساب المستلم:"), font_name=FONT_PATH, font_size='13sp', size_hint=(1, 0.12)))

        inp_phone = TextInput(text=self.saved_whatsapp_number, font_name=FONT_PATH, multiline=False, size_hint=(1, 0.15), halign='center')
        box.add_widget(inp_phone)

        checks_grid = GridLayout(cols=2, spacing=6, size_hint=(1, 0.38))
        cb_plate = CheckBox(active=True, size_hint=(0.2, 1))
        lbl_plate = Label(text=ar("بيانات اللوحة والسيارة"), font_name=FONT_PATH, font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_plate)
        checks_grid.add_widget(cb_plate)

        cb_loc = CheckBox(active=True, size_hint=(0.2, 1))
        lbl_loc = Label(text=ar("الموقع الجغرافي (GPS دقيق)"), font_name=FONT_PATH, font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_loc)
        checks_grid.add_widget(cb_loc)

        cb_camera = CheckBox(active=False, size_hint=(0.2, 1))
        lbl_camera = Label(text=ar("📸 تصوير السيارة بالكاميرا"), font_name=FONT_PATH, font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_camera)
        checks_grid.add_widget(cb_camera)
        box.add_widget(checks_grid)

        btn_send = Button(text=ar("🚀 فتح الواتساب وإرسال التقرير"), font_name=FONT_PATH, font_size='14sp', bold=True,
                          background_color=(0.1, 0.7, 0.3, 1), size_hint=(1, 0.2))
        box.add_widget(btn_send)

        pop = Popup(title=ar("تخصيص وإرسال الهدف"), title_font=FONT_PATH, content=box, size_hint=(0.92, 0.72))

        def send_action(x):
            phone = inp_phone.text.strip().replace("+", "")
            self.saved_whatsapp_number = phone

            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO config (key, value) VALUES ("wa_number", ?)', (phone,))
            conn.commit()
            conn.close()

            report_lines = ["🚨 *تقرير رصد تكتيكي - تطبيق القناص PRO* 🚨", "━━━━━━━━━━━━━━━━━"]
            if cb_plate.active:
                report_lines.append(f"📌 *اللوحة:* {self.current_target['plate']}")
                report_lines.append(f"🚗 *الموديل:* {self.current_target['model']}")
                report_lines.append(f"🆔 *الشاص:* {self.current_target['chassis']}")
                report_lines.append(f"🏢 *الجهة:* {self.current_target['bank']}")
                report_lines.append(f"🕒 *الوقت:* {self.current_target['time']}")

            if cb_loc.active:
                lat, lon = self.get_precise_location()
                if lat is not None and lon is not None:
                    report_lines.append("━━━━━━━━━━━━━━━━━")
                    report_lines.append(f"📍 *الموقع الميداني (خرائط جوجل):*\nhttps://maps.google.com/?q={lat:.6f},{lon:.6f}")
                else:
                    report_lines.append("\n⚠️ تعذر جلب إحداثيات GPS بدقة")

            self.pending_report_text = "\n".join(report_lines)
            pop.dismiss()

            if cb_camera.active:
                self.capture_car_photo()
            else:
                self._dispatch_to_whatsapp(phone, self.pending_report_text, None)

        btn_send.bind(on_press=send_action)
        pop.open()

    def _dispatch_to_whatsapp(self, phone, text_msg, image_path=None):
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                File = autoclass('java.io.File')

                if image_path and os.path.exists(image_path):
                    intent = Intent(Intent.ACTION_SEND)
                    intent.setType("image/jpeg")
                    intent.setPackage("com.whatsapp")
                    file_uri = Uri.fromFile(File(image_path))
                    intent.putExtra(Intent.EXTRA_STREAM, file_uri)
                    intent.putExtra(Intent.EXTRA_TEXT, text_msg)
                    intent.putExtra("jid", f"{phone}@s.whatsapp.net")
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                else:
                    encoded = urllib.parse.quote(text_msg)
                    wa_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded}"
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(wa_url))

                PythonActivity.mActivity.startActivity(intent)
                return
            except Exception as e:
                print("WhatsApp dispatch error:", e)

        encoded = urllib.parse.quote(text_msg)
        wa_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded}"
        import webbrowser
        webbrowser.open(wa_url)

    def show_hit_history(self, instance):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT plate, model, chassis, bank, created_at FROM hits_log ORDER BY id DESC LIMIT 15')
        rows = c.fetchall()
        conn.close()

        txt = "\n\n".join([f"• {r[0]} | {r[1]} | {r[2]} ({r[4]})" for r in rows]) if rows else "لا توجد أهداف مسجلة حتى الآن."

        box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        lbl = Label(text=ar(txt), font_name=FONT_PATH, font_size='13sp', halign='center')
        lbl.bind(size=lbl.setter('text_size'))
        box.add_widget(lbl)

        btn = Button(text=ar("إغلاق"), font_name=FONT_PATH, size_hint=(1, 0.2))
        box.add_widget(btn)

        pop = Popup(title=ar("سجل الأهداف المكتشفة"), title_font=FONT_PATH, content=box, size_hint=(0.88, 0.75))
        btn.bind(on_press=pop.dismiss)
        pop.open()

if __name__ == '__main__':
    AlknasApp().run()
