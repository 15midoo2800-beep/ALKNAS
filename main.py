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

def clean_cell_value(val):
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

class AlknasApp(App):
    def build(self):
        self.tts = None
        self.current_target = None
        self.saved_whatsapp_number = "966500000000"
        self.pending_photo_path = None
        self.pending_report_text = ""

        if platform == 'android':
            self.db_name = os.path.join(self.user_data_dir, "plates.db")
        else:
            self.db_name = "plates.db"

        root = BoxLayout(orientation='vertical', padding=12, spacing=8)

        # 1. الشريط العلوي
        header = BoxLayout(orientation='horizontal', size_hint=(1, 0.08))
        self.lbl_targets = Label(
            text=ar("الأهداف: جاري الفحص..."),
            font_name=FONT_PATH,
            font_size='13sp',
            color=(0.2, 1.0, 0.5, 1),
            size_hint=(0.5, 1)
        )
        header.add_widget(self.lbl_targets)

        self.lbl_title = Label(
            text=ar("القناص 🎯"),
            font_name=FONT_PATH,
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.5, 1)
        )
        header.add_widget(self.lbl_title)
        root.add_widget(header)

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
            text=ar("📁 استيراد ملف (CSV/Excel)"),
            font_name=FONT_PATH,
            font_size='13sp',
            background_color=(0.1, 0.35, 0.25, 1)
        )
        self.btn_import.bind(on_press=self.open_system_file_picker)
        ctrl_bar.add_widget(self.btn_import)
        root.add_widget(ctrl_bar)

        # 3. حقل إدخال اللوحة
        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة (مثال: 1955 ح هـ ن)"),
            font_name=FONT_PATH,
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
            font_name=FONT_PATH,
            font_size='16sp',
            bold=True,
            background_color=(0.85, 0.15, 0.2, 1)
        )
        self.btn_voice.bind(on_press=self.start_voice_recognition)
        action_bar.add_widget(self.btn_voice)

        self.btn_search = Button(
            text=ar("🔍 فحص اللوحة"),
            font_name=FONT_PATH,
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
            font_name=FONT_PATH,
            font_size='16sp',
            halign='center',
            valign='middle',
            color=(0.8, 0.85, 0.9, 1),
            size_hint=(1, 0.53)
        )
        self.result_panel.bind(size=self.result_panel.setter('text_size'))
        root.add_widget(self.result_panel)

        # 6. زر إرسال واتساب
        self.btn_whatsapp = Button(
            text=ar("🚀 إرسال الموقع والبيانات للواتساب"),
            font_name=FONT_PATH,
            font_size='15sp',
            bold=True,
            background_color=(0.1, 0.7, 0.3, 1),
            size_hint=(1, 0.1)
        )
        self.btn_whatsapp.bind(on_press=self.open_whatsapp_dialog)
        self.btn_whatsapp.opacity = 0
        self.btn_whatsapp.disabled = True
        root.add_widget(self.btn_whatsapp)

        Clock.schedule_once(self._safe_startup, 0.4)
        return root

    def _safe_startup(self, dt):
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

    def get_precise_location(self):
        if platform != 'android':
            return 24.7136, 46.6753

        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            activity = PythonActivity.mActivity
            location_service = activity.getSystemService(Context.LOCATION_SERVICE)

            providers = ['gps', 'network', 'passive']
            best_location = None

            for p in providers:
                try:
                    if location_service.isProviderEnabled(p):
                        loc = location_service.getLastKnownLocation(p)
                        if loc is not None:
                            if best_location is None or loc.getTime() > best_location.getTime():
                                best_location = loc
                except Exception:
                    continue

            if best_location is not None:
                return best_location.getLatitude(), best_location.getLongitude()
        except Exception as e:
            print("Location error:", e)

        return None, None

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

        elif request_code == 3003:
            photo_to_send = self.pending_photo_path if (self.pending_photo_path and os.path.exists(self.pending_photo_path)) else None
            Clock.schedule_once(lambda dt: self._dispatch_to_whatsapp(self.saved_whatsapp_number, self.pending_report_text, photo_to_send), 0)

    def _apply_search(self, text_val):
        self.input_plate.text = text_val
        self.search_plate(text_val)

    def _handle_file_import(self, uri):
        self.result_panel.text = ar("جاري استيراد ومعالجة الملف...")
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

            self._import_worker(temp_path)
        except Exception as e:
            if pfd:
                try: pfd.close()
                except Exception: pass
            Clock.schedule_once(lambda dt: self._done_import(0, str(e)), 0)

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
                    Clock.schedule_once(lambda dt: self._done_import(0, f"تعذر قراءة XLS: {e}"), 0)
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
            Clock.schedule_once(lambda dt: self._done_import(0, f"خطأ بالملف: {e}"), 0)

    def _import_worker(self, file_path):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('PRAGMA synchronous = OFF')
        c.execute('PRAGMA journal_mode = MEMORY')
        c.execute('DELETE FROM vehicles')

        count = 0
        batch = []
        try:
            for row in self._iter_rows(file_path):
                if row and str(row[0]).strip():
                    r0 = str(row[0]).strip()
                    if any(header_word in r0 for header_word in ['لوحة', 'اللوحة', 'plate', 'Plate']):
                        continue

                    digits, letters = clean_input(r0)
                    clean = digits + letters
                    
                    other_cols = [str(col).strip() for col in row[1:4]]
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

                    batch.append((clean, digits, letters, r0, chassis, bank, model))
                    count += 1
                    if len(batch) >= 5000:
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
            Clock.schedule_once(lambda dt: self._done_import(count, None), 0)
        except Exception as e:
            conn.close()
            Clock.schedule_once(lambda dt: self._done_import(0, str(e)), 0)

    def _done_import(self, cnt, err):
        if err:
            self.result_panel.text = ar(f"تنبيه:\n{err}")
        else:
            self.result_panel.text = ar(f"اكتمل الاستيراد بنجاح!\nتمت إضافة {cnt:,} سيارة مقروءة.")
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
            self.result_panel.text = ar(f"اللوحة ({query})\nليست مسجلة ضمن الأهداف المطلوبة.")
            self.result_panel.color = (0.85, 0.4, 0.4, 1)
            self.btn_whatsapp.opacity = 0
            self.btn_whatsapp.disabled = True

    def open_whatsapp_dialog(self, instance):
        if not self.current_target:
            return

        box = BoxLayout(orientation='vertical', padding=10, spacing=8)
        box.add_widget(Label(text=ar("رقم الواتساب المستلم (مع كود الدولة):"), font_name=FONT_PATH, font_size='13sp', size_hint=(1, 0.12)))
        
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
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("wa_number", ?)', (phone,))
            conn.commit()
            conn.close()

            report_lines = ["🚨 *تقرير رصد - تطبيق القناص* 🚨", "━━━━━━━━━━━━━━━━━"]
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
                    report_lines.append(f"📍 *الموقع الميداني الدقيق (خرائط جوجل):*\nhttps://maps.google.com/?q={lat:.6f},{lon:.6f}")
                else:
                    report_lines.append("\n⚠️ لم يتم التقاط إحداثيات GPS (تأكد من تفعيل الموقع بالهاتف)")

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
