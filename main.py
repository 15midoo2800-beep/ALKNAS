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
from kivy.uix.filechooser import FileChooserListView
from kivy.utils import platform

# مكتبات تصحيح وعرض العربية
import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = "font.ttf" if os.path.exists("font.ttf") else "Roboto"

def ar(text):
    """تجهيز وتصحيح النص العربي ليعرض بشكل سليم في Kivy"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

def normalize_text(text):
    """تطبيع النصوص العربية وتوحيد الهمزات وحذف المسافات للبحث الميداني الموثوق"""
    if not text:
        return ""
    t = str(text).strip()
    t = re.sub(r'[\s\-_\/]+', '', t)
    t = re.sub(r'[إأآا]', 'ا', t)
    t = re.sub(r'ة', 'ه', t)
    t = re.sub(r'ى', 'ي', t)
    return t.upper()

class AlknasApp(App):
    def build(self):
        self.db_name = "plates.db"
        self.tts = None
        self.init_database()

        # الواجهة الرئيسية
        root = BoxLayout(orientation='vertical', padding=12, spacing=8)

        # 1. شريط الإحصائيات العلوي
        self.stats_bar = Label(
            text=ar(f"السيارات المسجلة: {self.get_total_records()} | الحالة: جاهز"),
            font_name=FONT_PATH,
            font_size='13sp',
            size_hint=(1, 0.05),
            color=(0.7, 0.8, 0.9, 1)
        )
        root.add_widget(self.stats_bar)

        # 2. أزرار التحكم العلوية (استيراد ملف + سجل الأهداف)
        top_ctrl = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.08))
        
        self.btn_import = Button(
            text=ar("📂 استيراد ملف (CSV/Excel)"),
            font_name=FONT_PATH,
            font_size='14sp',
            background_color=(0.15, 0.45, 0.35, 1)
        )
        self.btn_import.bind(on_press=self.open_file_chooser)
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

        # 3. حقل البحث
        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة (أرقام أو حروف)..."),
            font_name=FONT_PATH,
            multiline=False,
            size_hint=(1, 0.09),
            font_size='18sp'
        )
        root.add_widget(self.input_plate)

        # 4. أزرار الفحص (فحص عادي + فحص صوتي سريع)
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

        # 5. لوحة النتائج التفاعلية
        self.result_panel = Label(
            text=ar("جاهز للرصد الميداني.\nانطق أو اكتب رقم اللوحة."),
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
                plate_clean TEXT UNIQUE,
                plate_original TEXT,
                chassis_number TEXT,
                bank_name TEXT,
                car_model TEXT
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_plate_clean ON vehicles(plate_clean)')
        
        # جدول لحفظ سجل الأهداف المرصودة
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
        """تهيئة الميكروفون، الاهتزاز، ومحرك نطق الصوت (TTS)"""
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
            activity.bind(on_activity_result=self.on_voice_result)

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
            Locale = autoclass('java.util.Locale')

            # إنشاء محرك النطق
            self.tts = TextToSpeech(PythonActivity.mActivity, None)
        except Exception as e:
            print("Android feature init error:", e)

    def trigger_alert(self, text_alert):
        """إطلاق اهتزاز قوي وتنبيه صوتي"""
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Context = autoclass('android.content.Context')
                activity = PythonActivity.mActivity
                vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
                
                # نمط اهتزاز تحذيري متكرر
                pattern = [0, 400, 150, 400, 150, 600]
                vibrator.vibrate(pattern, -1)
            except Exception as e:
                print("Vibrate error:", e)

            # النطق الصوتي التلقائي
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
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "انطق رقم اللوحة...")

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 1001)
        except Exception as e:
            self.result_panel.text = ar(f"خطأ في فتح المايك: {str(e)}")

    def on_voice_result(self, request_code, result_code, data):
        if request_code == 1001 and data is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    raw_text = str(results.get(0)).strip()
                    self.input_plate.text = raw_text
                    self.search_plate(raw_text)
            except Exception as e:
                self.result_panel.text = ar(f"خطأ في قراءة الصوت: {str(e)}")

    def search_plate(self, query):
        clean_q = normalize_text(query)
        if not clean_q:
            self.result_panel.text = ar("يرجى إدخال أو نطق رقم اللوحة!")
            self.result_panel.color = (1, 0.7, 0, 1)
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # بحث مطابق أولاً
        c.execute('''
            SELECT plate_original, chassis_number, bank_name, car_model 
            FROM vehicles 
            WHERE plate_clean = ?
        ''', (clean_q,))
        row = c.fetchone()

        # إذا لم يُعثر عليها، تجربة بحث جزئي إذا كان الإدخال أرقاماً فقط
        if not row and clean_q.isdigit() and len(clean_q) >= 3:
            c.execute('''
                SELECT plate_original, chassis_number, bank_name, car_model 
                FROM vehicles 
                WHERE plate_clean LIKE ?
                LIMIT 1
            ''', (f"%{clean_q}%",))
            row = c.fetchone()

        if row:
            plate_val, chassis, bank, model = row
            # حفظ في سجل الأهداف
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
            self.result_panel.text = ar(res_text)
            self.result_panel.color = (0.1, 1, 0.2, 1)  # أخضر فاقع
            self.trigger_alert(f"هدف مطلوب! {bank} {model}")
        else:
            conn.close()
            self.result_panel.text = ar(f"اللوحة ({query}) ليست في القائمة المطلوبة.")
            self.result_panel.color = (0.9, 0.3, 0.3, 1)

    def show_hit_history(self, instance):
        """عرض الأهداف السابقة التي عثر عليها الراصد"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT plate, bank, model, created_at FROM hits_log ORDER BY id DESC LIMIT 15')
        rows = c.fetchall()
        conn.close()

        if not rows:
            content_text = "لا توجد أهداف مسجلة حتى الآن."
        else:
            lines = []
            for r in rows:
                lines.append(f"• {r[0]} | {r[1]} | {r[2]} ({r[3]})")
            content_text = "\n\n".join(lines)

        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        lbl = Label(text=ar(content_text), font_name=FONT_PATH, font_size='14sp', halign='center')
        lbl.bind(size=lbl.setter('text_size'))
        popup_layout.add_widget(lbl)

        btn_close = Button(text=ar("إغلاق"), font_name=FONT_PATH, size_hint=(1, 0.2))
        popup_layout.add_widget(btn_close)

        pop = Popup(title=ar("سجل الصيد الميداني"), content=popup_layout, size_hint=(0.9, 0.8))
        btn_close.bind(on_press=pop.dismiss)
        pop.open()

    def open_file_chooser(self, instance):
        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        start_path = "/sdcard/Download" if os.path.exists("/sdcard/Download") else os.path.expanduser("~")
        
        chooser = FileChooserListView(path=start_path, filters=['*.csv', '*.xlsx', '*.txt'])
        popup_layout.add_widget(chooser)

        ctrl = BoxLayout(size_hint=(1, 0.15), spacing=10)
        btn_sel = Button(text=ar("تأكيد الاستيراد"), font_name=FONT_PATH)
        btn_can = Button(text=ar("إلغاء"), font_name=FONT_PATH)
        ctrl.add_widget(btn_sel)
        ctrl.add_widget(btn_can)
        popup_layout.add_widget(ctrl)

        pop = Popup(title=ar("اختر ملف البيانات"), content=popup_layout, size_hint=(0.95, 0.95))

        def on_confirm(b):
            if chooser.selection:
                selected_file = chooser.selection[0]
                pop.dismiss()
                self.start_import_thread(selected_file)
            else:
                self.result_panel.text = ar("لم تحدد أي ملف!")

        btn_sel.bind(on_press=on_confirm)
        btn_can.bind(on_press=pop.dismiss)
        pop.open()

    def start_import_thread(self, file_path):
        """تشغيل الاستيراد في مسار منفصل لمنع تجميد الشاشة"""
        self.result_panel.text = ar("جاري معالجة واستيراد البيانات في الخلفية...")
        self.result_panel.color = (1, 0.8, 0.2, 1)
        threading.Thread(target=self._import_worker, args=(file_path,), daemon=True).start()

    def _import_worker(self, file_path):
        batch = []
        batch_size = 5000
        count = 0

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        try:
            if file_path.endswith('.csv') or file_path.endswith('.txt'):
                with open(file_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 1 and row[0].strip():
                            orig = row[0].strip()
                            clean = normalize_text(orig)
                            chassis = row[1].strip() if len(row) > 1 else ""
                            bank = row[2].strip() if len(row) > 2 else ""
                            model = row[3].strip() if len(row) > 3 else ""
                            batch.append((clean, orig, chassis, bank, model))
                            count += 1

                            if len(batch) >= batch_size:
                                c.executemany('''
                                    INSERT OR REPLACE INTO vehicles (plate_clean, plate_original, chassis_number, bank_name, car_model)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', batch)
                                conn.commit()
                                batch.clear()

            elif file_path.endswith('.xlsx'):
                from openpyxl import load_workbook
                wb = load_workbook(filename=file_path, read_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    if row and row[0]:
                        orig = str(row[0]).strip()
                        clean = normalize_text(orig)
                        chassis = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                        bank = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                        model = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                        batch.append((clean, orig, chassis, bank, model))
                        count += 1

                        if len(batch) >= batch_size:
                            c.executemany('''
                                INSERT OR REPLACE INTO vehicles (plate_clean, plate_original, chassis_number, bank_name, car_model)
                                VALUES (?, ?, ?, ?, ?)
                            ''', batch)
                            conn.commit()
                            batch.clear()
                wb.close()

            if batch:
                c.executemany('''
                    INSERT OR REPLACE INTO vehicles (plate_clean, plate_original, chassis_number, bank_name, car_model)
                    VALUES (?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()

            conn.close()
            Clock.schedule_once(lambda dt: self._import_done(count, None), 0)

        except Exception as e:
            conn.close()
            Clock.schedule_once(lambda dt: self._import_done(0, str(e)), 0)

    def _import_done(self, count, error):
        if error:
            self.result_panel.text = ar(f"تعذر استيراد الملف:\n{error}")
            self.result_panel.color = (0.9, 0.2, 0.2, 1)
        else:
            self.result_panel.text = ar(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {count:,} سيارة.")
            self.result_panel.color = (0.2, 0.9, 0.2, 1)
            self.stats_bar.text = ar(f"السيارات المسجلة: {self.get_total_records()} | الحالة: محدث")

if __name__ == '__main__':
    AlknasApp().run()
