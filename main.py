import os
import csv
import sqlite3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.utils import platform

# مكتبات دعم اللغة العربية
import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = "font.ttf" if os.path.exists("font.ttf") else "Roboto"

def ar(text):
    """تجهيز وتصحيح النص العربي ليعرض بشكل سليم في واجهات Kivy"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

class AlknasApp(App):
    def build(self):
        self.db_name = "plates.db"
        self.init_database()

        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

        # 1. عنوان التطبيق
        self.title_label = Label(
            text=ar("نظام القناص - رصد وبحث اللوحات"),
            font_size='22sp',
            font_name=FONT_PATH,
            size_hint=(1, 0.09),
            color=(0.2, 0.6, 1, 1)
        )
        layout.add_widget(self.title_label)

        # 2. زر استيراد ملف البيانات
        self.load_file_btn = Button(
            text=ar("📂 استيراد ملف البيانات (CSV / Excel)"),
            font_name=FONT_PATH,
            size_hint=(1, 0.09),
            font_size='16sp',
            background_color=(0.2, 0.5, 0.3, 1)
        )
        self.load_file_btn.bind(on_press=self.open_file_chooser)
        layout.add_widget(self.load_file_btn)

        # 3. حقل إدخال رقم اللوحة
        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة هنا أو استخدم الصوت..."),
            font_name=FONT_PATH,
            multiline=False,
            size_hint=(1, 0.09),
            font_size='18sp'
        )
        layout.add_widget(self.input_plate)

        # 4. صف أزرار البحث (بحث يدوي + بحث صوتي)
        search_box = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.1))
        
        self.search_btn = Button(
            text=ar("🔍 بحث"),
            font_name=FONT_PATH,
            font_size='18sp',
            background_color=(0.1, 0.4, 0.7, 1)
        )
        self.search_btn.bind(on_press=lambda x: self.search_plate(self.input_plate.text))
        search_box.add_widget(self.search_btn)

        self.voice_btn = Button(
            text=ar("🎙️ بحث صوتي"),
            font_name=FONT_PATH,
            font_size='18sp',
            background_color=(0.8, 0.3, 0.2, 1)
        )
        self.voice_btn.bind(on_press=self.start_voice_recognition)
        search_box.add_widget(self.voice_btn)

        layout.add_widget(search_box)

        # 5. شاشة عرض النتائج
        self.result_label = Label(
            text=ar("جاهز للبحث. انطق رقم اللوحة أو اكتبه."),
            font_name=FONT_PATH,
            font_size='16sp',
            size_hint=(1, 0.63),
            halign='center',
            valign='middle',
            color=(1, 1, 1, 1)
        )
        self.result_label.bind(size=self.result_label.setter('text_size'))
        layout.add_widget(self.result_label)

        # تجهيز لاقط الصوت الخاص بأندرويد
        if platform == 'android':
            self.init_android_voice()

        return layout

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT UNIQUE,
                chassis_number TEXT,
                bank_name TEXT,
                car_model TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_plate ON vehicles(plate_number)')
        conn.commit()
        conn.close()

    def init_android_voice(self):
        """ربط نشاط أندرويد لاستقبال نتيجة الصوت"""
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            
            from jnius import autoclass
            from android import activity
            activity.bind(on_activity_result=self.on_voice_result)
        except Exception as e:
            print("Voice init error:", e)

    def start_voice_recognition(self, instance):
        """تشغيل نافذة التعرف على الصوت المدمجة في أندرويد"""
        if platform != 'android':
            self.result_label.text = ar("البحث الصوتي يعمل مباشرة على هاتف الأندرويد")
            return

        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar-SA")  # اللغة العربية
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "انطق رقم اللوحة...")

            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 1001)
        except Exception as e:
            self.result_label.text = ar(f"تعذر فتح المايك: {str(e)}")

    def on_voice_result(self, request_code, result_code, data):
        """استقبال النتيجة الصوتية بعد انتهاء المستخدم من النطق"""
        if request_code == 1001 and data is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    recognized_text = str(results.get(0)).strip()
                    # تنظيف النص واستخراج الأرقام/الأحرف
                    cleaned_query = "".join(recognized_text.split())
                    self.input_plate.text = cleaned_query
                    self.search_plate(cleaned_query)
            except Exception as e:
                self.result_label.text = ar(f"خطأ في معالجة الصوت: {str(e)}")

    def open_file_chooser(self, instance):
        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        start_path = "/sdcard/Download" if os.path.exists("/sdcard/Download") else os.path.expanduser("~")
        
        file_chooser = FileChooserListView(
            path=start_path,
            filters=['*.csv', '*.xlsx', '*.txt']
        )
        popup_layout.add_widget(file_chooser)

        btn_box = BoxLayout(size_hint=(1, 0.15), spacing=10)
        select_btn = Button(text=ar("تأكيد الاختيار"), font_name=FONT_PATH)
        cancel_btn = Button(text=ar("إلغاء"), font_name=FONT_PATH)

        btn_box.add_widget(select_btn)
        btn_box.add_widget(cancel_btn)
        popup_layout.add_widget(btn_box)

        popup = Popup(
            title=ar("اختر ملف البيانات"),
            content=popup_layout,
            size_hint=(0.95, 0.95)
        )

        def on_select(btn):
            if file_chooser.selection:
                selected_file = file_chooser.selection[0]
                popup.dismiss()
                self.import_file_data(selected_file)
            else:
                self.result_label.text = ar("لم يتم اختيار أي ملف!")

        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()

    def import_file_data(self, file_path):
        self.result_label.text = ar("جاري استيراد البيانات، يرجى الانتظار...")
        count = 0
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            if file_path.endswith('.csv') or file_path.endswith('.txt'):
                with open(file_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 1 and row[0].strip():
                            plate = "".join(row[0].strip().split())
                            chassis = row[1].strip() if len(row) > 1 else ""
                            bank = row[2].strip() if len(row) > 2 else ""
                            model = row[3].strip() if len(row) > 3 else ""
                            cursor.execute('''
                                INSERT OR REPLACE INTO vehicles (plate_number, chassis_number, bank_name, car_model)
                                VALUES (?, ?, ?, ?)
                            ''', (plate, chassis, bank, model))
                            count += 1

            elif file_path.endswith('.xlsx'):
                from openpyxl import load_workbook
                wb = load_workbook(filename=file_path, read_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    if row and row[0]:
                        plate = "".join(str(row[0]).strip().split())
                        chassis = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                        bank = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                        model = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                        cursor.execute('''
                            INSERT OR REPLACE INTO vehicles (plate_number, chassis_number, bank_name, car_model)
                            VALUES (?, ?, ?, ?)
                        ''', (plate, chassis, bank, model))
                        count += 1
                wb.close()

            conn.commit()
            conn.close()
            self.result_label.text = ar(f"تم بنجاح استيراد {count} سيارة إلى قاعدة البيانات!")
            self.result_label.color = (0.2, 0.9, 0.2, 1)

        except Exception as e:
            conn.close()
            self.result_label.text = ar(f"حدث خطأ أثناء قراءة الملف:\n{str(e)}")
            self.result_label.color = (0.9, 0.2, 0.2, 1)

    def search_plate(self, query):
        query = "".join(str(query).strip().split())
        if not query:
            self.result_label.text = ar("يرجى إدخال أو نطق رقم اللوحة")
            self.result_label.color = (1, 0.7, 0, 1)
            return

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT plate_number, chassis_number, bank_name, car_model 
            FROM vehicles 
            WHERE plate_number = ?
        ''', (query,))
        row = cursor.fetchone()
        conn.close()

        if row:
            res_text = (
                f"🚨 تم العثور على هدف!\n\n"
                f"اللوحة: {row[0]}\n"
                f"الشاص: {row[1]}\n"
                f"الجهة / البنك: {row[2]}\n"
                f"نوع السيارة: {row[3]}"
            )
            self.result_label.text = ar(res_text)
            self.result_label.color = (0.2, 0.9, 0.2, 1)
        else:
            self.result_label.text = ar(f"اللوحة ({query}) غير مطلوبة")
            self.result_label.color = (0.8, 0.2, 0.2, 1)

if __name__ == '__main__':
    AlknasApp().run()
