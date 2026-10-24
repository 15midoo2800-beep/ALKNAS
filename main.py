import os
import json
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase

# معالجة النصوص العربية لضمان ظهورها متصلة وصحيحة 100%
HAS_ARABIC_FIX = False
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_FIX = True
except ImportError:
    pass

def arabic_text(text):
    if not text:
        return ""
    if HAS_ARABIC_FIX:
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            return get_display(reshaped_text)
        except:
            return text
    return text

# تسجيل الخط العربي (تأكد من وجود font.ttf في المستودع)
font_path = 'font.ttf'
if os.path.exists(font_path):
    try:
        LabelBase.register(name='ArabicFont', fn_regular=font_path)
    except Exception as e:
        print(f"خطأ في تسجيل الخط: {e}")

class FieldManagementManager:
    def __init__(self, app_instance):
        self.app_instance = app_instance
        self.current_district = "النهضة"
        self.current_street = "ض 1"
        self.street_map_link = ""
        self.current_note = "بدون ملاحظة"
        
        # قائمة الملاحظات الميدانية الجاهزة
        self.predefined_notes = [
            "بدون ملاحظة",
            "برحة يمين",
            "برحة يسار",
            "برحة آخر الشارع",
            "برحة نهاية الشارع",
            "برحة منتصف الشارع",
            "برحة وسط الشارع",
            "برحة يمين أول الشارع",
            "برحة يسار أول الشارع",
            "تحت تندة"
        ]

    def set_location(self, district, street, map_link=""):
        self.current_district = district if district else "غير محدد"
        self.current_street = street if street else "غير محدد"
        self.street_map_link = map_link

    def set_note(self, note):
        self.current_note = note if note else "بدون ملاحظة"

    def save_record_locally(self, plate_text):
        """حفظ السجلات محلياً بمسار آمن داخل أندرويد"""
        try:
            safe_dir = self.app_instance.user_data_dir
            os.makedirs(safe_dir, exist_ok=True)
            file_path = os.path.join(safe_dir, "alknas_records.json")

            record = {
                "التاريخ": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "الحي": self.current_district,
                "الشارع": self.current_street,
                "الملاحظة": self.current_note,
                "لوحة_البحث": plate_text,
                "الموقع": self.street_map_link
            }

            data = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    data = []

            data.append(record)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            return file_path
        except Exception as e:
            print(f"خطأ في الحفظ المحلي: {e}")
            return ""

class AlknasApp(App):
    def build(self):
        self.field_manager = FieldManagementManager(self)
        current_font = 'ArabicFont' if os.path.exists(font_path) else 'Roboto'
        
        root_layout = BoxLayout(orientation='vertical', padding=10, spacing=8)
        
        # العنوان الرئيسي
        self.header_label = Label(
            text=arabic_text("تطبيق القناص - نظام الرصد الميداني"), 
            font_name=current_font,
            font_size=18, 
            size_hint=(1, 0.08)
        )
        root_layout.add_widget(self.header_label)
        
        # لوحة معلومات النطاق الحالي (الحي والشارع والملاحظة)
        self.update_info_text()
        self.info_label = Label(
            text=self.info_display_text,
            font_name=current_font,
            font_size=13,
            size_hint=(1, 0.12)
        )
        root_layout.add_widget(self.info_label)
        
        # شاشة البحث وإدخال اللوحات (مشابهة للفيديوهات)
        search_layout = BoxLayout(orientation='horizontal', spacing=5, size_hint=(1, 0.1))
        self.search_input = TextInput(
            hint_text=arabic_text("اكتب أو انطق رقم اللوحة للبحث..."),
            font_name=current_font,
            size_hint=(0.75, 1)
        )
        btn_search = Button(
            text=arabic_text("بحث ورصد"),
            font_name=current_font,
            size_hint=(0.25, 1)
        )
        btn_search.bind(on_press=self.perform_search_and_record)
        search_layout.add_widget(self.search_input)
        search_layout.add_widget(btn_search)
        root_layout.add_widget(search_layout)
        
        # أزرار التحكم والعمليات الميدانية
        controls_layout = GridLayout(cols=2, spacing=8, size_hint=(1, 0.3))
        
        btn_set_location = Button(text=arabic_text("تحديد الحي والشارع"), font_name=current_font)
        btn_set_location.bind(on_press=self.open_location_popup)
        controls_layout.add_widget(btn_set_location)
        
        btn_set_note = Button(text=arabic_text("الملاحظات السريعة"), font_name=current_font)
        btn_set_note.bind(on_press=self.open_notes_popup)
        controls_layout.add_widget(btn_set_note)
        
        btn_clear = Button(text=arabic_text("مسح السجل"), font_name=current_font)
        btn_clear.bind(on_press=self.clear_log)
        controls_layout.add_widget(btn_clear)
        
        btn_status = Button(text=arabic_text("حالة النظام"), font_name=current_font)
        btn_status.bind(on_press=self.show_status)
        controls_layout.add_widget(btn_status)
        
        root_layout.add_widget(controls_layout)
        
        # شاشة سجل الرصد والمتابعة
        self.log_input = TextInput(
            text=arabic_text("--- جاهز للرصد والبحث الميداني ---\n"),
            font_name=current_font,
            readonly=True,
            size_hint=(1, 0.3)
        )
        root_layout.add_widget(self.log_input)
        
        return root_layout

    def update_info_text(self):
        raw_text = f"الحي: {self.field_manager.current_district} | الشارع: {self.field_manager.current_street}\nالملاحظة: {self.field_manager.current_note}"
        self.info_display_text = arabic_text(raw_text)

    def open_location_popup(self, instance):
        current_font = 'ArabicFont' if os.path.exists(font_path) else 'Roboto'
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        district_input = TextInput(text=self.field_manager.current_district, hint_text=arabic_text("اسم الحي"), font_name=current_font)
        street_input = TextInput(text=self.field_manager.current_street, hint_text=arabic_text("اسم الشارع"), font_name=current_font)
        
        def save_location(btn):
            self.field_manager.set_location(district_input.text, street_input.text)
            self.update_info_text()
            self.info_label.text = self.info_display_text
            popup.dismiss()
            
        save_btn = Button(text=arabic_text("حفظ النطاق"), font_name=current_font, size_hint=(1, 0.3))
        save_btn.bind(on_press=save_location)
        
        content.add_widget(district_input)
        content.add_widget(street_input)
        content.add_widget(save_btn)
        
        popup = Popup(title=arabic_text("ضبط الموقع الجغرافي"), content=content, size_hint=(0.8, 0.5))
        popup.open()

    def open_notes_popup(self, instance):
        current_font = 'ArabicFont' if os.path.exists(font_path) else 'Roboto'
        content = BoxLayout(orientation='vertical', spacing=5, padding=10)
        
        spinner = Spinner(
            text=self.field_manager.current_note,
            values=self.field_manager.predefined_notes,
            font_name=current_font,
            size_hint=(1, 0.3)
        )
        
        def save_note(btn):
            self.field_manager.set_note(spinner.text)
            self.update_info_text()
            self.info_label.text = self.info_display_text
            popup.dismiss()
            
        save_btn = Button(text=arabic_text("اعتماد الملاحظة"), font_name=current_font, size_hint=(1, 0.3))
        save_btn.bind(on_press=save_note)
        
        content.add_widget(spinner)
        content.add_widget(save_btn)
        
        popup = Popup(title=arabic_text("الملاحظات الميدانية السريعة"), content=content, size_hint=(0.8, 0.4))
        popup.open()

    def perform_search_and_record(self, instance):
        plate = self.search_input.text.strip()
        if not plate:
            self.log_input.text += "\n" + arabic_text("[تنبيه]: يرجى إدخال أو نطق رقم اللوحة أولاً.")
            return
            
        path = self.field_manager.save_record_locally(plate)
        if path:
            msg = f"[تم الرصد بنجاح]: اللوحة ({plate}) | الحي ({self.field_manager.current_district}) - ({self.field_manager.current_note})"
            self.log_input.text += "\n" + arabic_text(msg)
            self.search_input.text = ""
        else:
            self.log_input.text += "\n" + arabic_text("[خطأ في الحفظ]")

    def clear_log(self, instance):
        self.log_input.text = arabic_text("--- تم مسح السجل ---")

    def show_status(self, instance):
        self.log_input.text += "\n" + arabic_text("[النظام يعمل بكفاءة]: واجهة البحث والنطاق جاهزة.")

if __name__ == '__main__':
    AlknasApp().run()
