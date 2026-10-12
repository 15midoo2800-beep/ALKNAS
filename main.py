import os
import csv
import re
import sqlite3
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

# دالة آمنة للنصوص العربية لا تسبب إغلاق التطبيق نهائياً
def ar(text):
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
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

class AlknasApp(App):
    def build(self):
        self.tts = None
        self.current_target = None
        self.saved_whatsapp_number = "966500000000"
        
        # المسار الآمن لقاعدة البيانات على الهاتف
        if platform == 'android':
            self.db_name = os.path.join(self.user_data_dir, "plates.db")
        else:
            self.db_name = "plates.db"

        # واجهة تكتيكية داكنة مستقرة لا تنهار
        root = BoxLayout(orientation='vertical', padding=12, spacing=8)

        # 1. الشريط العلوي
        header = BoxLayout(orientation='horizontal', size_hint=(1, 0.08))
        self.lbl_targets = Label(
            text=ar("الأهداف: جاري التحميل..."),
            font_size='13sp',
            color=(0.2, 1.0, 0.5, 1),
            size_hint=(0.5, 1)
        )
        header.add_widget(self.lbl_targets)

        self.lbl_title = Label(
            text=ar("القناص 🎯"),
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.5, 1)
        )
        header.add_widget(self.lbl_title)
        root.add_widget(header)

        # 2. أزرار التحكم العلوية
        ctrl_bar = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.08))
        self.btn_history = Button(
            text=ar("📋 سجل الأهداف"),
            font_size='13sp',
            background_color=(0.15, 0.2, 0.3, 1)
        )
        self.btn_history.bind(on_press=self.show_hit_history)
        ctrl_bar.add_widget(self.btn_history)

        self.btn_import = Button(
            text=ar("📁 استيراد ملف (CSV/Excel)"),
            font_size='13sp',
            background_color=(0.1, 0.35, 0.25, 1)
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        ctrl_bar.add_widget(self.btn_import)
        root.add_widget(ctrl_bar)

        # 3. حقل إدخال رقم اللوحة
        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة (مثال: 1955 ح هـ ن)"),
            multiline=False,
            font_size='22sp',
            halign='center',
            size_hint=(1, 0.11),
            background_color=(0.95, 0.95, 0.98, 1),
            foreground_color=(0.05, 0.05, 0.05, 1),
            padding=[8, 12]
        )
        root.add_widget(self.input_plate)

        # 4. أزرار الفحص
        action_bar = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.1))
        self.btn_voice = Button(
            text=ar("🎙️ فحص بالصوت"),
            font_size='16sp',
            bold=True,
            background_color=(0.85, 0.15, 0.2, 1)
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_bar.add_widget(self.btn_voice)

        self.btn_search = Button(
            text=ar("🔍 فحص اللوحة"),
            font_size='16sp',
            bold=True,
            background_color=(0.1, 0.45, 0.85, 1)
        )
        self.btn_search.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        action_bar.add_widget(self.btn_search)
        root.add_widget(action_bar)

        # 5. شاشة عرض النتيجة
        self.result_panel = Label(
            text=ar("رادار القناص نشط ومستعد.\n\nانطق رقم اللوحة أو اكتبه للفحص المباشر."),
            font_size='16sp',
            halign='center',
            valign='middle',
            color=(0.8, 0.85, 0.9, 1),
            size_hint=(1, 0.53)
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        root.add_widget(self.result_panel)

        # 6. زر إرسال واتساب (مخفي افتراضياً ويظهر عند اصطياد سيارة)
        self.btn_whatsapp = Button(
            text=ar("🚀 إرسال الموقع والبيانات للواتساب"),
            font_size='15sp',
            bold=True,
            background_color=(0.1, 0.7, 0.3, 1),
            size_hint=(1, 0.1)
        )
        self.btn_whatsapp.bind(on_press=self.open_whatsapp_dialog)
        self.btn_whatsapp.opacity = 0
        self.btn_whatsapp.disabled = True
        root.add_widget(self.btn_whatsapp)

        # تهيئة الخدمات لاحقاً لمنع الإغلاق في أول ثانية
        Clock.schedule_once(self._safe_startup, 0.5)

        return root

    def _safe_startup(self, dt):
        """تهيئة قاعدة البيانات والصلاحيات بأمان بعد ظهور الشاشة"""
        try:
            self.init_database()
            self.lbl_targets.text = ar(f"الأهداف: {self.get_total_records()} | جاهز")
        except Exception as e:
            print("DB init error:", e)

        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.RECORD_AUDIO,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.VIBRATE,
                    Permission.ACCESS_FINE_LOCATION,
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
        c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('SELECT value FROM settings WHERE key="wa_number"')
        row = c.fetchone()
        if row:
            self.saved_whatsapp_number = row[0]
        else:
            c.execute('INSERT INTO settings VALUES ("wa_number", "966500000000")')
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

    def start_voice_recognition(self, instance):
        if platform != 'android':
            self.result_panel.text = ar("البحث الصوتي يعمل على الأندرويد.")
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

    def on_activity_callback(self, request_code, result_code, data):
        if request_code == 1001 and data is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    val = str(results.get(0)).strip()
                    Clock.schedule_once(lambda dt: self._apply_search(val), 0)
            except Exception:
                pass

        elif request_code == 2002 and data is not None:
            try:
                uri = data.getData()
                if uri is not None:
                    Clock.schedule_once(lambda dt: self._handle_file_import(uri), 0)
            except Exception as e:
                self.result_panel.text = ar(f"خطأ: {e}")

    def _apply_search(self, text_val):
        self.input_plate.text = text_val
        self.search_plate(text_val)

    def _handle_file_import(self, uri):
        self.result_panel.text = ar("جاري معالجة واستيراد الملف... انتظر لحظات")
        threading.Thread(target=self._copy_and_read, args=(uri,), daemon=True).start()

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

            self._import_data(temp_path)
        except Exception as e:
            if pfd:
                try: pfd.close()
                except Exception: pass
            Clock.schedule_once(lambda dt: self._done_import(0, str(e)), 0)

    def _import_data(self, file_path):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('PRAGMA synchronous = OFF')
        c.execute('PRAGMA journal_mode = MEMORY')
        c.execute('DELETE FROM vehicles')

        count = 0
        batch = []
        try:
            # قراءة ملفات CSV
            with open(file_path, mode='r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and str(row[0]).strip():
                        r0 = str(row[0]).strip()
                        digits, letters = clean_input(r0)
                        clean = digits + letters
                        model = str(row[1]).strip() if len(row) > 1 else ""
                        chassis = str(row[2]).strip() if len(row) > 2 else ""
                        bank = str(row[3]).strip() if len(row) > 3 else ""

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
            self.result_panel.text = ar(f"تنبيه:\n{err}")
        else:
            self.result_panel.text = ar(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {cnt:,} سيارة.")
            self.lbl_targets.text = ar(f"الأهداف: {self.get_total_records()} | جاهز")

    def search_plate(self, query):
        digits_q, letters_q = clean_input(query)
        if not digits_q and not letters_q:
            self.result_panel.text = ar("يرجى إدخال أو نطق رقم اللوحة أولاً!")
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        row = None

        if digits_q and letters_q:
            c.execute('SELECT plate_original, chassis_number, bank_name, car_model FROM vehicles WHERE digits_only = ? LIMIT 1', (digits_q,))
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
            res = f"🚨 تم رصد هدف مطلوب! 🚨\n\nاللوحة: {plate}\nالموديل: {model}\nالشاص: {chassis}\nالجهة: {bank}"
            self.result_panel.text = ar(res)
            self.result_panel.color = (0.2, 1.0, 0.5, 1)

            # إظهار زر الواتساب الميداني
            self.btn_whatsapp.opacity = 1
            self.btn_whatsapp.disabled = False

            # اهتزاز وتنبيه صوتي
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
            self.result_panel.text = ar(f"اللوحة ({query})\nليست مسجلة ضمن الأهداف المطلوبة.")
            self.result_panel.color = (0.85, 0.4, 0.4, 1)
            self.btn_whatsapp.opacity = 0
            self.btn_whatsapp.disabled = True

    def open_whatsapp_dialog(self, instance):
        if not self.current_target:
            return

        box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        box.add_widget(Label(text=ar("رقم الواتساب المستلم:"), font_size='13sp', size_hint=(1, 0.15)))
        
        inp_phone = TextInput(text=self.saved_whatsapp_number, multiline=False, size_hint=(1, 0.18), halign='center')
        box.add_widget(inp_phone)

        btn_send = Button(text=ar("🚀 فتح الواتساب وإرسال الموقع والبيانات"), font_size='14sp', bold=True,
                          background_color=(0.1, 0.7, 0.3, 1), size_hint=(1, 0.25))
        box.add_widget(btn_send)

        pop = Popup(title=ar("إرسال تقرير الهدف"), content=box, size_hint=(0.9, 0.5))

        def send_action(x):
            phone = inp_phone.text.strip().replace("+", "")
            self.saved_whatsapp_number = phone
            
            # حفظ الرقم
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("wa_number", ?)', (phone,))
            conn.commit()
            conn.close()

            # تجهيز التقرير مع الموقع الميداني
            msg = (
                f"🚨 *تقرير رصد - تطبيق القناص* 🚨\n"
                f"📌 اللوحة: {self.current_target['plate']}\n"
                f"🚗 الموديل: {self.current_target['model']}\n"
                f"🆔 الشاص: {self.current_target['chassis']}\n"
                f"🏢 الجهة: {self.current_target['bank']}\n"
                f"🕒 الوقت: {self.current_target['time']}\n"
                f"📍 الموقع الميداني: https://maps.google.com"
            )

            encoded = urllib.parse.quote(msg)
            wa_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded}"

            if platform == 'android':
                try:
                    from jnius import autoclass
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    Intent = autoclass('android.content.Intent')
                    Uri = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(wa_url))
                    PythonActivity.mActivity.startActivity(intent)
                except Exception:
                    pass

            pop.dismiss()

        btn_send.bind(on_press=send_action)
        pop.open()

    def show_hit_history(self, instance):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT plate, model, chassis, bank, created_at FROM hits_log ORDER BY id DESC LIMIT 15')
        rows = c.fetchall()
        conn.close()

        txt = "\n\n".join([f"• {r[0]} | {r[1]} | {r[2]} ({r[4]})" for r in rows]) if rows else "لا توجد أهداف مسجلة حتى الآن."
        
        box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        lbl = Label(text=ar(txt), font_size='13sp', halign='center')
        lbl.bind(size=lbl.setter('text_size'))
        box.add_widget(lbl)

        btn = Button(text=ar("إغلاق"), size_hint=(1, 0.2))
        box.add_widget(btn)

        pop = Popup(title=ar("سجل الأهداف المكتشفة"), content=box, size_hint=(0.88, 0.75))
        btn.bind(on_press=pop.dismiss)
        pop.open()

if __name__ == '__main__':
    AlknasApp().run()
