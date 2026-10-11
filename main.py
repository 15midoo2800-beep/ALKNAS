import os
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

ARABIC_TO_ENG = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

def normalize_digits(text):
    if not text:
        return ""
    text = str(text).translate(ARABIC_TO_ENG)
    return "".join(re.findall(r'\d+', text))

def clean_letters(text):
    if not text:
        return ""
    text = str(text).translate(ARABIC_TO_ENG)
    return "".join(re.findall(r'[^\d\s\u0660-\u0669\W]+', text))

class AlknasApp(App):
    def build(self):
        self.title = "القناص - رصد السيارات"
        self.db_path = "hunter_database.db"
        self.init_database()

        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

        # عنوان رئيسي
        self.header = Label(
            text="🚗 محرك القناص الميداني 🚗",
            size_hint_y=None,
            height=45,
            font_size='20sp',
            bold=True
        )
        layout.add_widget(self.header)

        # خانة البحث
        self.search_input = TextInput(
            hint_text="أدخل أرقام أو حروف اللوحة (مثال: 4535 أو رمط)",
            multiline=False,
            size_hint_y=None,
            height=50,
            font_size='18sp'
        )
        self.search_input.bind(on_text_validate=self.search_vehicle)
        layout.add_widget(self.search_input)

        # زر البحث
        self.search_btn = Button(
            text="بحث فوري",
            size_hint_y=None,
            height=50,
            background_color=(0.1, 0.6, 0.9, 1),
            font_size='18sp'
        )
        self.search_btn.bind(on_press=self.search_vehicle)
        layout.add_widget(self.search_btn)

        # منطقة النتائج التمريرية
        scroll = ScrollView(size_hint=(1, 1))
        self.result_label = Label(
            text="جاهز للبحث...",
            size_hint_y=None,
            markup=True,
            font_size='16sp'
        )
        self.result_label.bind(texture_size=self.result_label.setter('size'))
        scroll.add_widget(self.result_label)
        layout.add_widget(scroll)

        return layout

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_full TEXT,
            plate_letters TEXT,
            plate_digits TEXT,
            model TEXT,
            bank TEXT,
            vin TEXT
        )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_digits ON vehicles (plate_digits)')
        conn.commit()
        conn.close()

    def search_vehicle(self, instance):
        query = self.search_input.text.strip()
        if not query:
            self.result_label.text = "يرجى كتابة رقم أو حروف للبحث."
            return

        digits = normalize_digits(query)
        letters = clean_letters(query)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        if digits:
            cur.execute("""
                SELECT plate_full, plate_letters, model, bank, vin 
                FROM vehicles 
                WHERE plate_digits = ?
            """, (digits,))
        else:
            cur.execute("""
                SELECT plate_full, plate_letters, model, bank, vin 
                FROM vehicles 
                WHERE plate_letters = ?
            """, (letters,))

        matches = cur.fetchall()

        if letters and len(matches) > 1:
            filtered = [c for c in matches if letters in c[1] or c[1] in letters]
            if filtered:
                matches = filtered

        conn.close()

        if matches:
            res_text = f"[color=ff3333]🚨 [تنبيه: سيارة مطلوبة!] ({len(matches)} مطابقة):[/color]\n\n"
            for idx, car in enumerate(matches, 1):
                res_text += f"🔹 {idx}) اللوحة: {car[0]} | الموديل: {car[2]}\n"
                res_text += f"    البنك: {car[3]} | الشاص: {car[4]}\n"
                res_text += "--------------------------------------\n"
            self.result_label.text = res_text
        else:
            self.result_label.text = f"[color=33cc33]⚪ سليمة (غير مطلوبة)[/color]\nرقم البحث: {digits or letters}"

if __name__ == '__main__':
    AlknasApp().run()
