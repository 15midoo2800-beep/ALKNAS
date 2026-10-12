import os
import csv
import re
import sqlite3
import threading
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.parse

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.utils import platform

# حماية معالجة النصوص العربية
def ar(text):
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
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

def fix_mojibake(text):
    if not text:
        return ""
    t = str(text).strip()
    if any(c in t for c in ['ط', 'ظ', '¹', '§', '€', '±', 'ـ', '³']):
        for src_enc, dst_enc in [
            ('windows-1252', 'utf-8'),
            ('cp1256', 'utf-8'),
            ('latin1', 'utf-8'),
            ('utf-8', 'windows-1256')
        ]:
            try:
                fixed = t.encode(src_enc, errors='ignore').decode(dst_enc, errors='ignore')
                if any('\u0600' <= ch <= '\u06FF' for ch in fixed) and not any(bad in fixed for bad in ['ط±', 'ط¹', 'ط§', 'ط·', 'ظ']):
                    return fixed
            except Exception:
                continue
    return t

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
    t = fix_mojibake(t)
    t = str(t).translate(EASTERN_TO_WESTERN_DIGITS)
    t = re.sub(r'[إأآا]', 'ا', t)
    t = re.sub(r'ة', 'ه', t)
    t = re.sub(r'ى', 'ي', t)
    return t

def clean_cell_value(val):
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

def extract_tokens(text):
    if not text:
        return "", ""
    t = clean_speech_input(text)
    t = clean_arabic_chars(t)
    digits = "".join(re.findall(r'\d+', t))
    letters = "".join(re.findall(r'[\u0600-\u06FFa-zA-Z]+', t))
    return digits, letters

# كروت وأزرار محصنة تماماً ضد أخطاء OpenGL والأبعاد الصفرية
class GlowCard(BoxLayout):
    def __init__(self, bg_color=(0.04, 0.07, 0.09, 0.95), border_color=(0, 0.9, 0.45, 1),
                 radius=[18], line_width=1.5, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius = radius
        self.line_width = line_width
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
            if self.border_color:
                Color(*self.border_color)
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius[0]),
                     width=self.line_width)

class CyberPillButton(Button):
    def __init__(self, bg_color=(0.08, 0.12, 0.16, 1), border_color=(0.1, 0.6, 0.4, 0.8),
                 radius=[16], **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius = radius
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
            if self.border_color:
                Color(*self.border_color)
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius[0]),
                     width=1.2)

class PlateBox(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas.before:
            Color(0.12, 0.15, 0.19, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[18])
            Color(0.97, 0.98, 1.0, 1)
            RoundedRectangle(pos=(self.x + 6, self.y + 6),
                             size=(max(0, self.width - 12), max(0, self.height - 12)), radius=[14])
            Color(0.15, 0.15, 0.15, 1)
            Line(rounded_rectangle=(self.x + 8, self.y + 8, max(0, self.width - 16), max(0, self.height - 16), 12),
                 width=1.2)

class AlknasApp(App):
    def build(self):
        self.db_name = "plates.db"
        self.tts = None
        self.current_target = None
        self.saved_whatsapp_number = "966500000000"
        self.pending_photo_path = None
        self.pending_report_text = ""

        # الحاوية الرئيسية
        root = BoxLayout(orientation='vertical', padding=[14, 10], spacing=8)
        with root.canvas.before:
            Color(0.03, 0.04, 0.06, 1)
            self.bg_rect = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._update_bg, size=self._update_bg)

        # 1. شريط العنوان والعداد
        header = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), spacing=8)
        self.badge_box = GlowCard(
            bg_color=(0.04, 0.14, 0.09, 0.9),
            border_color=(0.1, 0.9, 0.45, 1),
            radius=[14],
            size_hint=(0.45, 1),
            padding=[4, 2]
        )
        self.lbl_targets = Label(
            text=ar("~ جاري الفحص ~\nأهداف مسجلة"),
            font_size='11sp',
            bold=True,
            halign='center',
            valign='middle',
            color=(0.2, 1.0, 0.5, 1)
        )
        self.lbl_targets.bind(size=self.lbl_targets.setter('text_size'))
        self.badge_box.add_widget(self.lbl_targets)
        header.add_widget(self.badge_box)

        self.lbl_app_title = Label(
            text=ar("القناص 🎯"),
            font_size='22sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='right',
            valign='middle',
            size_hint=(0.55, 1)
        )
        self.lbl_app_title.bind(size=self.lbl_app_title.setter('text_size'))
        header.add_widget(self.lbl_app_title)
        root.add_widget(header)

        # 2. أزرار السجل والاستيراد
        top_actions = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, 0.07))
        self.btn_history = CyberPillButton(
            text=ar("📋 سجل الأهداف"),
            font_size='13sp',
            bold=True,
            bg_color=(0.08, 0.11, 0.16, 1),
            border_color=(0.2, 0.35, 0.5, 0.8),
            color=(0.85, 0.92, 1, 1)
        )
        self.btn_history.bind(on_press=self.show_hit_history)
        top_actions.add_widget(self.btn_history)

        self.btn_import = CyberPillButton(
            text=ar("📁 استيراد ملف"),
            font_size='13sp',
            bold=True,
            bg_color=(0.05, 0.16, 0.13, 1),
            border_color=(0.1, 0.65, 0.45, 0.9),
            color=(0.7, 1.0, 0.85, 1)
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        top_actions.add_widget(self.btn_import)
        root.add_widget(top_actions)

        # 3. إطار لوحة السيارة للإدخال
        plate_container = PlateBox(orientation='horizontal', size_hint=(1, 0.14), padding=[10, 6])
        self.input_plate = TextInput(
            hint_text=ar("١٩٥٥ ح هـ ن"),
            multiline=False,
            size_hint=(0.82, 1),
            font_size='24sp',
            bold=True,
            background_color=(0, 0, 0, 0),
            foreground_color=(0.08, 0.08, 0.08, 1),
            halign='center',
            padding=[4, 14]
        )
        plate_container.add_widget(self.input_plate)

        ksa_side = Label(
            text="🇸🇦\nKSA",
            font_size='11sp',
            bold=True,
            color=(0.1, 0.4, 0.2, 1),
            size_hint=(0.18, 1),
            halign='center',
            valign='middle'
        )
        ksa_side.bind(size=ksa_side.setter('text_size'))
        plate_container.add_widget(ksa_side)
        root.add_widget(plate_container)

        # 4. أزرار الفحص
        action_row = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.085))
        self.btn_voice = CyberPillButton(
            text=ar("🎙️ فحص بالصوت"),
            font_size='15sp',
            bold=True,
            bg_color=(0.35, 0.05, 0.08, 0.9),
            border_color=(0.95, 0.15, 0.25, 1),
            color=(1, 0.85, 0.88, 1)
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_row.add_widget(self.btn_voice)

        self.btn_search = CyberPillButton(
            text=ar("🔍 فحص اللوحة"),
            font_size='15sp',
            bold=True,
            bg_color=(0.05, 0.22, 0.38, 0.9),
            border_color=(0.0, 0.75, 1.0, 1),
            color=(0.85, 0.95, 1, 1)
        )
        self.btn_search.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        action_row.add_widget(self.btn_search)
        root.add_widget(action_row)

        # 5. بطاقة النتيجة
        self.result_card = GlowCard(
            bg_color=(0.03, 0.07, 0.08, 0.95),
            border_color=(0.0, 0.95, 0.45, 1),
            radius=[20],
            line_width=1.8,
            orientation='vertical',
            padding=[14, 8],
            spacing=4,
            size_hint=(1, 0.525)
        )
        self.badge_status = Label(
            text=ar("⚡ نتائج الفحص النشط ⚡"),
            font_size='13sp',
            bold=True,
            color=(0.3, 1.0, 0.6, 1),
            size_hint=(1, 0.14),
            halign='center',
            valign='middle'
        )
        self.badge_status.bind(size=self.badge_status.setter('text_size'))
        self.result_card.add_widget(self.badge_status)

        self.result_panel = Label(
            text=ar("رادار القناص نشط ومستعد.\n\nانطق رقم اللوحة أو اكتبه للفحص التلقائي."),
            font_size='15sp',
            halign='center',
            valign='middle',
            color=(0.7, 0.85, 0.8, 1),
            line_height=1.35,
            size_hint=(1, 0.68)
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        self.result_card.add_widget(self.result_panel)

        self.btn_send_whatsapp = CyberPillButton(
            text=ar("🚀 إرسال الموقع والبيانات للواتساب"),
            font_size='14sp',
            bold=True,
            bg_color=(0.05, 0.35, 0.15, 0.9),
            border_color=(0.1, 0.95, 0.45, 1),
            color=(1, 1, 1, 1),
            size_hint=(1, 0.18)
        )
        self.btn_send_whatsapp.bind(on_press=self.open_whatsapp_dispatch_dialog)
        self.btn_send_whatsapp.opacity = 0
        self.btn_send_whatsapp.disabled = True
        self.result_card.add_widget(self.btn_send_whatsapp)
        root.add_widget(self.result_card)

        # تأخير أي استعلامات أو عمليات حتى تستقر الشاشة بالكامل
        Clock.schedule_once(self._post_init, 0.4)

        return root

    def _update_bg(self, instance, *args):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size

    def _post_init(self, dt):
        try:
            if platform == 'android':
                self.db_name = os.path.join(self.user_data_dir, "plates.db")
            else:
                self.db_name = "plates.db"

            self.init_database()
            self.lbl_targets.text = ar(f"~ {self.get_total_records()} ~\nأهداف مسجلة")
        except Exception as e:
            print("DB Post Init Exception:", e)

        if platform == 'android':
            try:
                self.init_android_features()
            except Exception as e:
                print("Android Features Exception:", e)

    def init_database(self):
        try:
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
            c.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            c.execute('SELECT value FROM settings WHERE key="wa_number"')
            row = c.fetchone()
            if row:
                self.saved_whatsapp_number = row[0]
            else:
                c.execute('INSERT INTO settings VALUES ("wa_number", "966500000000")')
            conn.commit()
            conn.close()
        except Exception as e:
            print("init_database error:", e)

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

    def get_current_location(self):
        if platform != 'android':
            return 24.7136, 46.6753

        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            activity = PythonActivity.mActivity
            loc_service = activity.getSystemService(Context.LOCATION_SERVICE)

            loc = loc_service.getLastKnownLocation('gps')
            if not loc:
                loc = loc_service.getLastKnownLocation('network')

            if loc:
                return loc.getLatitude(), loc.getLongitude()
        except Exception as e:
            print("Location error:", e)
        return None, None

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
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar-EG")
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "انطق رقم اللوحة والحروف...")

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 1001)

        except Exception:
            self._set_msg("تعذر فتح الميكروفون حالياً.", (0.9, 0.3, 0.3, 1))

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
                print("Camera launch error:", e)

        self._dispatch_to_whatsapp(self.saved_whatsapp_number, self.pending_report_text, None)

    def on_activity_callback(self, request_code, result_code, data):
        if request_code == 1001:
            try:
                from jnius import autoclass
                Activity = autoclass('android.app.Activity')

                if result_code != Activity.RESULT_OK or data is None:
                    Clock.schedule_once(
                        lambda dt: self._set_msg("لم يتم التقاط الصوت (تأكد من نطق اللوحة بوضوح).", (1, 0.6, 0.2, 1)),
                        0
                    )
                    return

                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    raw_text = str(results.get(0)).strip()
                    cleaned_val = clean_speech_input(raw_text)
                    Clock.schedule_once(lambda dt: self._apply_voice_search(cleaned_val), 0)
                else:
                    Clock.schedule_once(lambda dt: self._set_msg("لم يتم التعرف على الكلمات.", (1, 0.6, 0.2, 1)), 0)

            except Exception:
                Clock.schedule_once(lambda dt: self._set_msg("خطأ أثناء استلام الصوت.", (0.9, 0.2, 0.2, 1)), 0)

        elif request_code == 2002 and data is not None:
            try:
                uri = data.getData()
                if uri is not None:
                    Clock.schedule_once(lambda dt: self._handle_selected_uri(uri), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_msg(f"خطأ بالملف: {e}", (0.9, 0.2, 0.2, 1)), 0)

        elif request_code == 3003:
            photo_to_send = self.pending_photo_path if (self.pending_photo_path and os.path.exists(self.pending_photo_path)) else None
            Clock.schedule_once(lambda dt: self._dispatch_to_whatsapp(self.saved_whatsapp_number, self.pending_report_text, photo_to_send), 0)

    def _apply_voice_search(self, parsed_text):
        self.input_plate.text = parsed_text
        self.search_plate(parsed_text)

    def _set_msg(self, msg, color=(0.7, 0.85, 0.8, 1)):
        self.result_panel.text = ar(msg)
        self.result_panel.color = color

    def _handle_selected_uri(self, uri):
        self._set_msg("جاري استيراد ومعالجة الملف... يرجى الانتظار", (1, 0.8, 0.2, 1))
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

            temp_path = os.path.join(self.user_data_dir, "imported_data_temp")

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

    def _parse_xlsx_safely(self, file_path):
        def col_letter_to_index(col_str):
            num = 0
            for c in col_str:
                if 'A' <= c <= 'Z':
                    num = num * 26 + (ord(c) - ord('A') + 1)
            return max(0, num - 1)

        with zipfile.ZipFile(file_path, 'r') as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns_s = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for elem in tree.findall('.//ns:si', ns_s):
                    text = "".join(t.text for t in elem.findall('.//ns:t', ns_s) if t.text)
                    shared_strings.append(text)

            sheet_files = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
            if not sheet_files:
                return

            target_sheet = max(sheet_files, key=lambda name: z.getinfo(name).file_size)

            sheet_xml = z.read(target_sheet)
            tree = ET.fromstring(sheet_xml)
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

            for row_elem in tree.findall('.//ns:row', ns):
                row_cells = {}
                max_idx = 0

                for cell in row_elem.findall('ns:c', ns):
                    ref = cell.attrib.get('r', '')
                    col_letters = "".join(filter(str.isalpha, ref)).upper()
                    col_idx = col_letter_to_index(col_letters) if col_letters else len(row_cells)
                    max_idx = max(max_idx, col_idx)

                    cell_type = cell.attrib.get('t', '')
                    val = ""

                    is_elem = cell.find('ns:is', ns)
                    if is_elem is not None:
                        val = "".join(t.text for t in is_elem.findall('.//ns:t', ns) if t.text)
                    else:
                        v_elem = cell.find('ns:v', ns)
                        if v_elem is not None and v_elem.text:
                            raw_v = v_elem.text
                            if cell_type == 's' and raw_v.isdigit():
                                s_idx = int(raw_v)
                                val = shared_strings[s_idx] if s_idx < len(shared_strings) else raw_v
                            else:
                                val = raw_v

                    row_cells[col_idx] = clean_cell_value(val)

                if row_cells:
                    current_row = [row_cells.get(i, "") for i in range(max_idx + 1)]
                    if any(current_row):
                        yield current_row

    def _iter_rows(self, file_path):
        try:
            with open(file_path, "rb") as f_check:
                header = f_check.read(8)

            if header.startswith(b'PK'):
                for row in self._parse_xlsx_safely(file_path):
                    yield row
                return

            if header.startswith(b'\xd0\xcf\x11\xe0'):
                try:
                    import xlrd
                    wb = xlrd.open_workbook(file_path)
                    sheet = wb.sheet_by_index(0)
                    for row_idx in range(sheet.nrows):
                        row = sheet.row_values(row_idx)
                        if any(row):
                            yield [clean_cell_value(c) for c in row]
                    return
                except Exception as e:
                    Clock.schedule_once(lambda dt: self._set_msg(f"تعذر فتح ملف XLS: {e}", (1, 0.4, 0.4, 1)), 0)
                    return

            encodings = ['windows-1256', 'cp1256', 'utf-8-sig', 'utf-8']
            chosen_enc = 'windows-1256'
            for enc in encodings:
                try:
                    with open(file_path, mode='r', encoding=enc) as test_f:
                        sample = test_f.read(4096)
                        if any('\u0600' <= ch <= '\u06FF' for ch in sample) and not ('ط' in sample and 'ظ' in sample):
                            chosen_enc = enc
                            break
                except Exception:
                    continue

            with open(file_path, mode='r', encoding=chosen_enc, errors='replace') as f:
                first_line = f.readline()
                delimiter = ';' if ';' in first_line else ('\t' if '\t' in first_line else ',')
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if row:
                        yield [clean_cell_value(c) for c in row]

        except Exception as e:
            Clock.schedule_once(lambda dt: self._set_msg(f"خطأ أثناء معالجة الملف: {e}", (1, 0.3, 0.3, 1)), 0)

    def _import_worker(self, file_path):
        batch = []
        batch_size = 5000
        count = 0

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        try:
            c.execute('PRAGMA synchronous = OFF')
            c.execute('PRAGMA journal_mode = MEMORY')
            c.execute('DELETE FROM vehicles')

            for row in self._iter_rows(file_path):
                if len(row) >= 1 and str(row[0]).strip():
                    raw_col0 = fix_mojibake(str(row[0]).strip())

                    if any(header_word in raw_col0 for header_word in ['لوحة', 'اللوحة', 'plate', 'Plate']):
                        continue

                    digits, letters = extract_tokens(raw_col0)
                    clean = digits + letters

                    other_cols = [fix_mojibake(str(col).strip()) for col in row[1:4]]
                    while len(other_cols) < 3:
                        other_cols.append("")

                    chassis = ""
                    remaining = []

                    for col in other_cols:
                        if not chassis and len(col) >= 10 and re.match(r'^[A-Za-z0-9]+$', col):
                            chassis = col
                        else:
                            remaining.append(col)

                    while len(remaining) < 2:
                        remaining.append("")

                    model = remaining[0]
                    bank = remaining[1]

                    batch.append((clean, digits, letters, raw_col0, chassis, bank, model))
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

        except Exception as e:
            conn.close()
            Clock.schedule_once(lambda dt: self._import_done(0, str(e)), 0)

    def _import_done(self, count, error):
        if error:
            self._set_msg(f"تنبيه:\n{error}", (0.9, 0.2, 0.2, 1))
        else:
            self._set_msg(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {count:,} سيارة مقروءة.", (0.2, 1.0, 0.5, 1))
            self.lbl_targets.text = ar(f"~ {self.get_total_records()} ~\nأهداف مسجلة")

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
            c.execute('INSERT INTO hits_log (plate, bank, model, chassis, created_at) VALUES (?, ?, ?, ?, ?)',
                      (plate_val, bank, model, chassis, now_str))
            conn.commit()
            conn.close()

            self.current_target = {
                "plate": plate_val,
                "model": model,
                "chassis": chassis,
                "bank": bank,
                "time": now_str
            }

            res_text = (
                f"🚨 اللوحة:  {plate_val}\n\n"
                f"🚗 الموديل:  {model}\n\n"
                f"🆔 الشاص:  {chassis}\n\n"
                f"🏢 الجهة:  {bank}"
            )
            self._set_msg(res_text, (0.2, 1.0, 0.5, 1))
            self.badge_status.text = ar("🚨 تم رصد هدف مطلوب في النظام! 🚨")
            self.badge_status.color = (1.0, 0.25, 0.3, 1)
            
            self.btn_send_whatsapp.opacity = 1
            self.btn_send_whatsapp.disabled = False
            
            self.trigger_alert(f"هدف مطلوب! {model}")
        else:
            conn.close()
            self.current_target = None
            display_val = f"{digits_q} {letters_q}".strip()
            self._set_msg(f"اللوحة ({display_val})\nليست مسجلة ضمن الأهداف المطلوبة.", (0.85, 0.4, 0.4, 1))
            self.badge_status.text = ar("⚡ نتائج الفحص النشط ⚡")
            self.badge_status.color = (0.3, 1.0, 0.6, 1)
            self.btn_send_whatsapp.opacity = 0
            self.btn_send_whatsapp.disabled = True

    def open_whatsapp_dispatch_dialog(self, instance):
        if not self.current_target:
            return

        box = BoxLayout(orientation='vertical', padding=12, spacing=10)

        box.add_widget(Label(text=ar("رقم الواتساب المستلم (مع كود الدولة):"), font_size='13sp', size_hint=(1, 0.12)))
        input_phone = TextInput(
            text=self.saved_whatsapp_number,
            multiline=False,
            font_size='15sp',
            size_hint=(1, 0.15),
            halign='center'
        )
        box.add_widget(input_phone)

        box.add_widget(Label(text=ar("تخصيص البيانات المرسلة:"), font_size='13sp', size_hint=(1, 0.12)))
        
        checks_grid = GridLayout(cols=2, spacing=6, size_hint=(1, 0.4))
        
        cb_plate = CheckBox(active=True, size_hint=(0.2, 1))
        lbl_plate = Label(text=ar("بيانات اللوحة والسيارة"), font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_plate)
        checks_grid.add_widget(cb_plate)

        cb_loc = CheckBox(active=True, size_hint=(0.2, 1))
        lbl_loc = Label(text=ar("الموقع الجغرافي (GPS خرائط)"), font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_loc)
        checks_grid.add_widget(cb_loc)

        cb_camera = CheckBox(active=False, size_hint=(0.2, 1))
        lbl_camera = Label(text=ar("📸 فتح الكاميرا وتصوير السيارة"), font_size='12sp', size_hint=(0.8, 1))
        checks_grid.add_widget(lbl_camera)
        checks_grid.add_widget(cb_camera)

        box.add_widget(checks_grid)

        btn_confirm = CyberPillButton(
            text=ar("🚀 تنفيذ وإرسال"),
            font_size='14sp',
            bold=True,
            bg_color=(0.1, 0.65, 0.35, 1),
            size_hint=(1, 0.2)
        )
        box.add_widget(btn_confirm)

        dialog = Popup(
            title=ar("تخصيص إرسال الهدف"),
            content=box,
            size_hint=(0.92, 0.75),
            background_color=(0.04, 0.06, 0.09, 0.96)
        )

        def do_send(x):
            phone = input_phone.text.strip().replace("+", "")
            self.saved_whatsapp_number = phone
            
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("wa_number", ?)', (phone,))
            conn.commit()
            conn.close()

            report_lines = ["🚨 *تقرير رصد ميداني - تطبيق القناص* 🚨", "━━━━━━━━━━━━━━━━━"]
            if cb_plate.active:
                report_lines.append(f"📌 *اللوحة:* {self.current_target['plate']}")
                report_lines.append(f"🚗 *الموديل:* {self.current_target['model']}")
                report_lines.append(f"🆔 *الشاص:* {self.current_target['chassis']}")
                report_lines.append(f"🏢 *الجهة:* {self.current_target['bank']}")
                report_lines.append(f"🕒 *الوقت:* {self.current_target['time']}")

            if cb_loc.active:
                lat, lon = self.get_current_location()
                if lat and lon:
                    map_url = f"https://maps.google.com/?q={lat},{lon}"
                    report_lines.append("━━━━━━━━━━━━━━━━━")
                    report_lines.append(f"📍 *الموقع الميداني (خرائط جوجل):*\n{map_url}")
                else:
                    report_lines.append("\n⚠️ يتعذر جلب إحداثيات GPS حالياً")

            self.pending_report_text = "\n".join(report_lines)
            dialog.dismiss()

            if cb_camera.active:
                self.capture_car_photo()
            else:
                self._dispatch_to_whatsapp(phone, self.pending_report_text, None)

        btn_confirm.bind(on_press=do_send)
        dialog.open()

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
                    encoded_text = urllib.parse.quote(text_msg)
                    wa_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded_text}"
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(wa_url))

                PythonActivity.mActivity.startActivity(intent)
                return
            except Exception as e:
                print("WhatsApp dispatch error:", e)

        encoded_text = urllib.parse.quote(text_msg)
        wa_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded_text}"
        import webbrowser
        webbrowser.open(wa_url)

    def show_hit_history(self, instance):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT plate, model, chassis, bank, created_at FROM hits_log ORDER BY id DESC LIMIT 20')
        rows = c.fetchall()
        conn.close()

        if not rows:
            content_text = "لا توجد أهداف مسجلة في السجل حتى الآن."
        else:
            lines = [f"• {r[0]} | {r[1]} | {r[2]} ({r[4]})" for r in rows]
            content_text = "\n\n".join(lines)

        popup_layout = BoxLayout(orientation='vertical', padding=14, spacing=12)
        lbl = Label(text=ar(content_text), font_size='14sp', halign='center', color=(0.9, 0.9, 0.9, 1))
        lbl.bind(size=lbl.setter('text_size'))
        popup_layout.add_widget(lbl)

        btn_close = CyberPillButton(text=ar("إغلاق السجل"), font_size='14sp', size_hint=(1, 0.18),
                                  bg_color=(0.1, 0.15, 0.22, 1), border_color=(0.3, 0.5, 0.7, 1))
        popup_layout.add_widget(btn_close)

        pop = Popup(
            title=ar("سجل الأهداف المكتشفة"),
            content=popup_layout,
            size_hint=(0.9, 0.82),
            background_color=(0.03, 0.04, 0.06, 0.96)
        )
        btn_close.bind(on_press=pop.dismiss)
        pop.open()

if __name__ == '__main__':
    AlknasApp().run()
