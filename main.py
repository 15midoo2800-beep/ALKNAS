import os
import sqlite3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button

# مكتبات معالجة اللغة العربية
import arabic_reshaper
from bidi.algorithm import get_display

FONT_PATH = "font.ttf" if os.path.exists("font.ttf") else "Roboto"

def ar(text):
    """دالة لتشبيك وعكس النص العربي ليظهر بالاتجاه الصحيح في Kivy"""
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

        # عنوان التطبيق
        self.title_label = Label(
            text=ar("نظام القناص - رصد وبحث اللوحات"),
            font_size='22sp',
            font_name=FONT_PATH,
            size_hint=(1, 0.12),
            color=(0.2, 0.6, 1, 1)
        )
        layout.add_widget(self.title_label)

        # حقل إدخال رقم اللوحة
        self.input_plate = TextInput(
            hint_text=ar("أدخل رقم اللوحة هنا..."),
            font_name=FONT_PATH,
            multiline=False,
            size_hint=(1, 0.12),
            font_size='18sp'
        )
        layout.add_widget(self.input_plate)

        # زر البحث
        self.search_btn = Button(
            text=ar("بحث"),
            font_name=FONT_PATH,
            size_hint=(1, 0.12),
            font_size='18sp',
            background_color=(0.1, 0.4, 0.7, 1)
        )
        self.search_btn.bind(on_press=self.search_plate)
        layout.add_widget(self.search_btn)

        # مساحة عرض النتائج
        self.result_label = Label(
            text=ar("في انتظار إدخال الرقم..."),
            font_name=FONT_PATH,
            font_size='16sp',
            size_hint=(1, 0.64),
            halign='center',
            valign='middle',
            color=(1, 1, 1, 1)
        )
        self.result_label.bind(size=self.result_label.setter('text_size'))
        layout.add_widget(self.result_label)

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
        # بيانات تجريبية للفحص
        cursor.execute('''
            INSERT OR IGNORE INTO vehicles (plate_number, chassis_number, bank_name, car_model)
            VALUES (?, ?, ?, ?)
        ''', ("9788", "CHAS123456789", "بنك الراجحي", "تويوتا كامري"))
        conn.commit()
        conn.close()

    def search_plate(self, instance):
        query = self.input_plate.text.strip()
        if not query:
            self.result_label.text = ar("يرجى إدخال رقم اللوحة أولاً")
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
                f"تم العثور على هدف!\n\n"
                f"اللوحة: {row[0]}\n"
                f"الشاص: {row[1]}\n"
                f"الجهة / البنك: {row[2]}\n"
                f"نوع السيارة: {row[3]}"
            )
            self.result_label.text = ar(res_text)
            self.result_label.color = (0.2, 0.9, 0.2, 1)  # لون أخضر
        else:
            self.result_label.text = ar(f"اللوحة {query} غير مطلوبة")
            self.result_label.color = (0.8, 0.2, 0.2, 1)  # لون أحمر

if __name__ == '__main__':
    AlknasApp().run()
