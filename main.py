import os
import csv
import re
import sqlite3
import threading
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
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

# مكونات الواجهة المخصصة بحواف منحنية وتصميم عصري
class RoundedButton(Button):
    def __init__(self, bg_color=(0.2, 0.45, 0.85, 1), radius=[14], **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.bg_color = bg_color
        self.radius = radius
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)

class RoundedCard(BoxLayout):
    def __init__(self, bg_color=(0.12, 0.15, 0.22, 1), radius=[16], **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)

class AlknasApp(App):
    def build(self):
        self.db_name = "plates.db"
        self.tts = None
        self.init_database()

        # حاوية التطبيق الأساسية بخلفية داكنة راقية
        root = BoxLayout(orientation='vertical', padding=14, spacing=10)
        with root.canvas.before:
            Color(0.07, 0.09, 0.13, 1)  # رمادي/كحلي ليلي فخم
            RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda obj, val: self._update_root_bg(root), size=lambda obj, val: self._update_root_bg(root))

        # 1. شريط التطبيق العلوي (AppBar Card)
        header_card = RoundedCard(bg_color=(0.11, 0.14, 0.20, 1), radius=[14], orientation='horizontal',
                                  padding=[12, 6], size_hint=(1, 0.08))
        self.title_lbl = Label(
            text=ar("🎯 القناص | ALKNAS"),
            font_name=FONT_PATH,
            font_size='16sp',
            bold=True,
            color=(0.95, 0.95, 0.98, 1),
            halign='left',
            size_hint=(0.45, 1)
        )
        self.title_lbl.bind(size=self.title_lbl.setter('text_size'))
        header_card.add_widget(self.title_lbl)

        self.stats_bar = Label(
            text=ar(f"الأهداف: {self.get_total_records()} | جاهز"),
            font_name=FONT_PATH,
            font_size='12sp',
            color=(0.4, 0.85, 0.65, 1),
            halign='right',
            size_hint=(0.55, 1)
        )
        self.stats_bar.bind(size=self.stats_bar.setter('text_size'))
        header_card.add_widget(self.stats_bar)
        root.add_widget(header_card)

        # 2. أزرار إدارة البيانات وسجل العمليات
        top_ctrl = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.08))
        self.btn_import = RoundedButton(
            text=ar("📂 استيراد ملف (CSV / Excel)"),
            font_name=FONT_PATH,
            font_size='13sp',
            bold=True,
            bg_color=(0.12, 0.38, 0.32, 1),  # Emerald Dark
            radius=[12]
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        top_ctrl.add_widget(self.btn_import)

        self.btn_history = RoundedButton(
            text=ar("📋 سجل الأهداف المكتشفة"),
            font_name=FONT_PATH,
            font_size='13sp',
            bold=True,
            bg_color=(0.25, 0.28, 0.38, 1),  # Slate Blue
            radius=[12]
        )
        self.btn_history.bind(on_press=self.show_hit_history)
        top_ctrl.add_widget(self.btn_history)
        root.add_widget(top_ctrl)

        # 3. حقل إدخال رقم اللوحة
        self.input_plate = TextInput(
            hint_text=ar("اكتب رقم اللوحة أو الحروف هنا..."),
            font_name=FONT_PATH,
            multiline=False,
            size_hint=(1, 0.09),
            font_size='18sp',
            background_color=(0.95, 0.96, 0.98, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            padding=[14, 12]
        )
        root.add_widget(self.input_plate)

        # 4. أزرار الإجراءات السريعة (البحث والصوت)
        action_box = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.1))
        self.btn_search = RoundedButton(
            text=ar("🔍 فحص اللوحة"),
            font_name=FONT_PATH,
            font_size='16sp',
            bold=True,
            bg_color=(0.15, 0.48, 0.85, 1),  # Material Vibrant Blue
            radius=[14]
        )
        self.btn_search.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        action_box.add_widget(self.btn_search)

        self.btn_voice = RoundedButton(
            text=ar("🎙️ فحص بالصوت"),
            font_name=FONT_PATH,
            font_size='16sp',
            bold=True,
            bg_color=(0.85, 0.22, 0.25, 1),  # Material Crimson
            radius=[14]
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_box.add_widget(self.btn_voice)
        root.add_widget(action_box)

        # 5. بطاقة عرض النتيجة المركزية الفاخرة
        self.result_card = RoundedCard(bg_color=(0.12, 0.15, 0.22, 1), radius=[18],
                                       padding=16, size_hint=(1, 0.65))
        self.result_panel = Label(
            text=ar("رادار القناص نشط ومستعد.\n\nانطق رقم اللوحة أو اكتبه للفحص الفوري."),
            font_name=FONT_PATH,
            font_size='16sp',
            halign='center',
            valign='middle',
            color=(0.75, 0.8, 0.88, 1),
            line_height=1.3
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        self.result_card.add_widget(self.result_panel)
        root.add_widget(self.result_card)

        if platform == 'android':
            Clock.schedule_once(lambda dt: self.init_android_features(), 0.5)

        return root

    def _update_root_bg(self, instance):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.07, 0.09, 0.13, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size)

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
            print("Android init error:", e)

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

    def _apply_voice_search(self, parsed_text):
        self.input_plate.text = parsed_text
        self.search_plate(parsed_text)

    def _set_msg(self, msg, color=(0.85, 0.9, 0.95, 1)):
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
            self._set_msg(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {count:,} سيارة مقروءة.", (0.2, 0.9, 0.2, 1))
            self.stats_bar.text = ar(f"الأهداف: {self.get_total_records()} | محدث")

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

            # عرض النتيجة بتصميم رادار فوري مميز
            res_text = (
                f"🚨 تم العثور على هدف مطلوب! 🚨\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"اللوحـة :  {plate_val}\n"
                f"الموديـل :  {model}\n"
                f"الشـاص :  {chassis}\n"
                f"الجهـة :  {bank}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            self._set_msg(res_text, (0.2, 1, 0.45, 1))  # لون أخضر نيون فسفوري للرصد
            self.trigger_alert(f"هدف مطلوب! {model}")
        else:
            conn.close()
            display_val = f"{digits_q} {letters_q}".strip()
            self._set_msg(f"اللوحة ({display_val})\nليست مسجلة ضمن الأهداف المطلوبة.", (0.85, 0.4, 0.4, 1))

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
        lbl = Label(text=ar(content_text), font_name=FONT_PATH, font_size='14sp', halign='center', color=(0.9, 0.9, 0.9, 1))
        lbl.bind(size=lbl.setter('text_size'))
        popup_layout.add_widget(lbl)

        btn_close = RoundedButton(text=ar("إغلاق السجل"), font_name=FONT_PATH, size_hint=(1, 0.18),
                                  bg_color=(0.25, 0.35, 0.5, 1), radius=[10])
        popup_layout.add_widget(btn_close)

        pop = Popup(
            title=ar("سجل الأهداف المكتشفة"),
            title_font=FONT_PATH,
            content=popup_layout,
            size_hint=(0.9, 0.82),
            background_color=(0.08, 0.1, 0.15, 0.95)
        )
        btn_close.bind(on_press=pop.dismiss)
        pop.open()

if __name__ == '__main__':
    AlknasApp().run()
