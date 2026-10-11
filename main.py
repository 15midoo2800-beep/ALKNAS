import os
import csv
import re
import sqlite3
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.utils import platform

import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = "font.ttf" if os.path.exists("font.ttf") else "Roboto"

def ar(text):
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

EASTERN_TO_WESTERN_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

LETTER_REPLACEMENTS = [
    (r'\b(الف|ألف|إلف|همزة)\b', 'ا'),
    (r'\b(باء|با|بي)\b', 'ب'),
    (r'\b(تاء|تا|تي)\b', 'ت'),
    (r'\b(ثاء|ثا)\b', 'ث'),
    (r'\b(جيم|جم)\b', 'ج'),
    (r'\b(حاء|حا)\b', 'ح'),
    (r'\b(خاء|خا)\b', 'خ'),
    (r'\b(دال|دا)\b', 'د'),
    (r'\b(ذال|ذا)\b', 'ذ'),
    (r'\b(راء|را|ري)\b', 'ر'),
    (r'\b(زاي|زا|زين)\b', 'ز'),
    (r'\b(سين|سا)\b', 'س'),
    (r'\b(شين|شا)\b', 'ش'),
    (r'\b(صاد|صا)\b', 'ص'),
    (r'\b(ضاد|ضا)\b', 'ض'),
    (r'\b(طاء|طا)\b', 'ط'),
    (r'\b(ظاء|ظا)\b', 'ظ'),
    (r'\b(عين|عا)\b', 'ع'),
    (r'\b(غين|غا)\b', 'غ'),
    (r'\b(فاء|فا|في)\b', 'ف'),
    (r'\b(قاف|قا)\b', 'ق'),
    (r'\b(كاف|كا)\b', 'ك'),
    (r'\b(لام|لا)\b', 'ل'),
    (r'\b(ميم|ما)\b', 'م'),
    (r'\b(نون|نا)\b', 'ن'),
    (r'\b(هاء|ها)\b', 'ه'),
    (r'\b(واو|وا)\b', 'و'),
    (r'\b(ياء|يا)\b', 'ي'),
    (r'\b(صفر)\b', '0'),
    (r'\b(واحد)\b', '1'),
    (r'\b(اثنين|إثنين)\b', '2'),
    (r'\b(تلاتة|ثلاثة)\b', '3'),
    (r'\b(اربعة|أربعة)\b', '4'),
    (r'\b(خمسة)\b', '5'),
    (r'\b(ستة)\b', '6'),
    (r'\b(سبعة)\b', '7'),
    (r'\b(تمانية|ثمانية)\b', '8'),
    (r'\b(تسعة)\b', '9'),
]

def clean_speech_input(text):
    if not text:
        return ""
    t = str(text).translate(EASTERN_TO_WESTERN_DIGITS)
    for pattern, repl in LETTER_REPLACEMENTS:
        t = re.sub(pattern, repl, t)
    return "".join(t.split())

def clean_arabic_chars(t):
    if not t:
        return ""
    t = str(t).translate(EASTERN_TO_WESTERN_DIGITS)
    t = re.sub(r'[إأآا]', 'ا', t)
    t = re.sub(r'ة', 'ه', t)
    t = re.sub(r'ى', 'ي', t)
    return t

def extract_tokens(text):
    if not text:
        return "", ""
    t = clean_speech_input(text)
    t = clean_arabic_chars(t)
    digits = "".join(re.findall(r'\d+', t))
    letters = "".join(re.findall(r'[\u0600-\u06FFa-zA-Z]+', t))
    return digits, letters

class AlknasApp(App):
    def build(self):
        self.db_name = "plates.db"
        self.tts = None
        self.init_database()

        root = BoxLayout(orientation='vertical', padding=12, spacing=8)

        self.stats_bar = Label(
            text=ar(f"السيارات المسجلة: {self.get_total_records()} | الحالة: جاهز"),
            font_name=FONT_PATH,
            font_size='13sp',
            size_hint=(1, 0.05),
            color=(0.7, 0.8, 0.9, 1)
        )
        root.add_widget(self.stats_bar)

        top_ctrl = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.08))
        self.btn_import = Button(
            text=ar("📂 استيراد ملف (CSV/Excel)"),
            font_name=FONT_PATH,
            font_size='14sp',
            background_color=(0.15, 0.45, 0.35, 1)
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        top_ctrl.add_widget(self.btn_import)

        self.btn_history = Button(
            text=ar("📋 سجل الأهداف"),
            font_name=FONT_PATH,
            font_size='14sp',
            background_color=(0.3, 0.3, 0.4, 1)
        )
        self.btn_history.bind(on_press=self.show_hit_history)
        top_ctrl.add_widget(self.btn_history)
        root.add_widget(top_ctrl)

        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة أو الحروف..."),
            font_name=FONT_PATH,
            multiline=False,
            size_hint=(1, 0.09),
            font_size='18sp'
        )
        root.add_widget(self.input_plate)

        action_box = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.1))
        self.btn_search = Button(
            text=ar("🔍 فحص اللوحة"),
            font_name=FONT_PATH,
            font_size='17sp',
            background_color=(0.1, 0.45, 0.75, 1)
        )
        self.btn_search.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        action_box.add_widget(self.btn_search)

        self.btn_voice = Button(
            text=ar("🎙️ فحص بالصوت"),
            font_name=FONT_PATH,
            font_size='17sp',
            background_color=(0.85, 0.25, 0.2, 1)
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_box.add_widget(self.btn_voice)
        root.add_widget(action_box)

        self.result_panel = Label(
            text=ar("جاهز للرصد الميداني.\nاكتب أو انطق رقم اللوحة."),
            font_name=FONT_PATH,
            font_size='17sp',
            size_hint=(1, 0.68),
            halign='center',
            valign='middle',
            color=(0.9, 0.9, 0.9, 1)
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        root.add_widget(self.result_panel)

        if platform == 'android':
            Clock.schedule_once(lambda dt: self.init_android_features(), 0.5)

        return root

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
                created_at TEXT
            )
        ''')
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

    def init_android_features(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.VIBRATE
            ])
            from jnius import autoclass
            from android import activity
            activity.bind(on_activity_result=self.on_activity_callback)

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
            self.tts = TextToSpeech(PythonActivity.mActivity, None)
        except Exception as e:
            print("Android feature init error:", e)

    def trigger_alert(self, text_alert):
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Context = autoclass('android.content.Context')
                activity = PythonActivity.mActivity
                vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
                pattern = [0, 400, 150, 400, 150, 600]
                vibrator.vibrate(pattern, -1)
            except Exception as e:
                print("Vibrate error:", e)

            if self.tts:
                try:
                    from jnius import autoclass
                    TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                    self.tts.speak(text_alert, TextToSpeech.QUEUE_FLUSH, None, "HIT_NOTIF")
                except Exception as e:
                    print("TTS error:", e)

    def start_voice_recognition(self, instance):
        if platform != 'android':
            self.result_panel.text = ar("البحث الصوتي يعمل على الأندرويد مباشرة.")
            return

        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar-SA")
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "انطق رقم اللوحة والحروف...")

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 1001)
        except Exception as e:
            self.result_panel.text = ar(f"خطأ في فتح المايك: {str(e)}")

    def open_system_file_picker(self, instance):
        if platform != 'android':
            self.result_panel.text = ar("اختيار الملف يعمل مباشرة على الهاتف.")
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
            self.result_panel.text = ar(f"تعذر فتح مدير الملفات: {str(e)}")

    def on_activity_callback(self, request_code, result_code, data):
        if request_code == 1001 and data is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    raw_text = str(results.get(0)).strip()
                    cleaned_val = clean_speech_input(raw_text)
                    Clock.schedule_once(lambda dt: self._apply_voice_search(cleaned_val), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_msg(f"خطأ بالصوت: {e}", (0.9, 0.2, 0.2, 1)), 0)

        elif request_code == 2002 and data is not None:
            try:
                uri = data.getData()
                if uri is not None:
                    Clock.schedule_once(lambda dt: self._handle_selected_uri(uri), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_msg(f"خطأ بالملف: {e}", (0.9, 0.2, 0.2, 1)), 0)

    def _apply_voice_search(self, parsed_text):
        self.input_plate.text = parsed_text
        self.search_plate(parsed_text)

    def _set_msg(self, msg, color=(1, 1, 1, 1)):
        self.result_panel.text = ar(msg)
        self.result_panel.color = color

    def _handle_selected_uri(self, uri):
        self._set_msg("جاري استيراد ومعالجة الملف...", (1, 0.8, 0.2, 1))
        threading.Thread(target=self._copy_and_import, args=(uri,), daemon=True).start()

    def _copy_and_import(self, uri):
        pfd = None
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            contentResolver = activity.getContentResolver()

            pfd = contentResolver.openFileDescriptor(uri, "r")
            fd = pfd.getFd()

            app_dir = App.get_running_app().user_data_dir
            temp_path = os.path.join(app_dir, "imported_data_temp")

            with open(fd, "rb", closefd=False) as src, open(temp_path, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)

            pfd.close()
            pfd = None

            self._import_worker(temp_path)

        except Exception as e:
            if pfd:
                try: pfd.close()
                except Exception: pass
            Clock.schedule_once(lambda dt: self._import_done(0, f"تعذر قراءة الملف: {str(e)}"), 0)

    def _import_worker(self, file_path):
        batch = []
        batch_size = 3000
        count = 0

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('DELETE FROM vehicles')

        # فحص أول بايتات من الملف لمعرفة إذا كان ملف مضغوط PK (Excel حقيقي)
        with open(file_path, "rb") as f_check:
            header = f_check.read(4)

        is_zip = header.startswith(b'PK')
        loaded = False

        if is_zip:
            try:
                from openpyxl import load_workbook
                wb = load_workbook(filename=file_path, read_only=True, data_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    if row and row[0]:
                        orig = str(row[0]).strip()
                        digits, letters = extract_tokens(orig)
                        clean = digits + letters
                        chassis = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                        bank = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                        model = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                        batch.append((clean, digits, letters, orig, chassis, bank, model))
                        count += 1

                        if len(batch) >= batch_size:
                            c.executemany('''
                                INSERT INTO vehicles (plate_clean, digits_only, letters_only, plate_original, chassis_number, bank_name, car_model)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', batch)
                            batch.clear()
                wb.close()
                loaded = True
            except Exception:
                loaded = False

        if not loaded:
            # تجربة قراءة الترميزات العربية الحقيقية بدقة
            encodings = ['cp1256', 'utf-8-sig', 'windows-1256', 'utf-16', 'utf-8']
            chosen_enc = 'cp1256'
            
            for enc in encodings:
                try:
                    with open(file_path, mode='r', encoding=enc) as f:
                        test_str = f.read(3000)
                        # التأكد من وجود حروف عربية سليمة وليس علامات استفهام وطلاسم
                        if any('\u0600' <= ch <= '\u06FF' for ch in test_str):
                            chosen_enc = enc
                            break
                except Exception:
                    continue

            with open(file_path, mode='r', encoding=chosen_enc, errors='ignore') as f:
                first_line = f.readline()
                delimiter = ';' if ';' in first_line else ('\t' if '\t' in first_line else ',')
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if len(row) >= 1 and str(row[0]).strip():
                        orig = str(row[0]).strip()
                        digits, letters = extract_tokens(orig)
                        clean = digits + letters
                        chassis = str(row[1]).strip() if len(row) > 1 else ""
                        bank = str(row[2]).strip() if len(row) > 2 else ""
                        model = str(row[3]).strip() if len(row) > 3 else ""
                        batch.append((clean, digits, letters, orig, chassis, bank, model))
                        count += 1

                        if len(batch) >= batch_size:
                            c.executemany('''
                                INSERT INTO vehicles (plate_clean, digits_only, letters_only, plate_original, chassis_number, bank_name, car_model)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', batch)
                            batch.clear()

        if batch:
            c.executemany('''
                INSERT INTO vehicles (plate_clean, digits_only, letters_only, plate_original, chassis_number, bank_name, car_model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', batch)

        conn.commit()
        conn.close()
        Clock.schedule_once(lambda dt: self._import_done(count, None), 0)

    def _import_done(self, count, error):
        if error:
            self._set_msg(f"تنبيه:\n{error}", (0.9, 0.2, 0.2, 1))
        else:
            self._set_msg(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {count:,} سيارة مقروءة.", (0.2, 0.9, 0.2, 1))
            self.stats_bar.text = ar(f"السيارات المسجلة: {self.get_total_records()} | الحالة: محدث")

    def search_plate(self, query):
        digits_q, letters_q = extract_tokens(query)
        if not digits_q and not letters_q:
            self._set_msg("يرجى إدخال أو نطق رقم اللوحة!", (1, 0.7, 0, 1))
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        row = None

        if digits_q and letters_q:
            rev_letters = letters_q[::-1]
            c.execute('''
                SELECT plate_original, chassis_number, bank_name, car_model 
                FROM vehicles 
                WHERE digits_only = ? AND (
                    letters_only = ? OR letters_only = ? OR 
                    letters_only LIKE ? OR letters_only LIKE ?
                )
                LIMIT 1
            ''', (digits_q, letters_q, rev_letters, f"%{letters_q}%", f"%{rev_letters}%"))
            row = c.fetchone()

        if not row and digits_q:
            c.execute('''
                SELECT plate_original, chassis_number, bank_name, car_model 
                FROM vehicles 
                WHERE digits_only = ?
                LIMIT 1
            ''', (digits_q,))
            row = c.fetchone()

        if not row:
            clean_all = digits_q + letters_q
            c.execute('''
                SELECT plate_original, chassis_number, bank_name, car_model 
                FROM vehicles 
                WHERE plate_clean LIKE ?
                LIMIT 1
            ''', (f"%{clean_all}%",))
            row = c.fetchone()

        if row:
            plate_val, chassis, bank, model = row
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute('INSERT INTO hits_log (plate, bank, model, created_at) VALUES (?, ?, ?, ?)',
                      (plate_val, bank, model, now_str))
            conn.commit()
            conn.close()

            res_text = (
                f"🚨 تم العثور على هدف مطلوب! 🚨\n\n"
                f"اللوحة: {plate_val}\n"
                f"الجهة: {bank}\n"
                f"الموديل: {model}\n"
                f"الشاص: {chassis}"
            )
            self._set_msg(res_text, (0.1, 1, 0.2, 1))
            self.trigger_alert(f"هدف مطلوب! {bank} {model}")
        else:
            conn.close()
            display_val = f"{digits_q} {letters_q}".strip()
            self._set_msg(f"اللوحة ({display_val}) ليست في القائمة المطلوبة.", (0.9, 0.3, 0.3, 1))

    def show_hit_history(self, instance):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT plate, bank, model, created_at FROM hits_log ORDER BY id DESC LIMIT 15')
        rows = c.fetchall()
        conn.close()

        if not rows:
            content_text = "لا توجد أهداف مسجلة حتى الآن."
        else:
            lines = [f"• {r[0]} | {r[1]} | {r[2]} ({r[3]})" for r in rows]
            content_text = "\n\n".join(lines)

        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        lbl = Label(text=ar(content_text), font_name=FONT_PATH, font_size='14sp', halign='center')
        lbl.bind(size=lbl.setter('text_size'))
        popup_layout.add_widget(lbl)

        btn_close = Button(text=ar("إغلاق"), font_name=FONT_PATH, size_hint=(1, 0.2))
        popup_layout.add_widget(btn_close)

        pop = Popup(
            title=ar("سجل الصيد الميداني"),
            title_font=FONT_PATH,
            content=popup_layout,
            size_hint=(0.9, 0.8)
        )
        btn_close.bind(on_press=pop.dismiss)
        pop.open()

if __name__ == '__main__':
    AlknasApp().run()
