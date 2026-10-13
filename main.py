import os
import uuid
import hashlib
from datetime import datetime
import urllib.parse
import webbrowser

# محاولة استخدام أدوات تشكيل النصوص العربية
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def ar(text):
        if not text:
            return ""
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
except ImportError:
    def ar(text):
        return str(text)

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import StringProperty, NumericProperty

# تسجيل خط عربي يدعم التشكيل
if os.path.exists("font.ttf"):
    LabelBase.register(name="AppFont", fn_regular="font.ttf")
    APP_FONT = "AppFont"
else:
    APP_FONT = "Roboto"

SALT = "ALKNAS_PRO_SECURITY_2026"
LICENSE_FILE = "license.dat"
WHATSAPP_NUMBER = "201155661920"

KV = '''
<MainLayout>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: 0.05, 0.07, 0.1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # الشريط العلوي
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "55dp"
        padding: ["12dp", "0dp", "12dp", "0dp"]
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.16, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: root.txt_header_status
            font_name: root.font_name
            font_size: "15sp"
            color: 0.2, 0.85, 0.45, 1
            halign: "left"
            valign: "middle"
            text_size: self.size

        Label:
            text: root.txt_app_title
            font_name: root.font_name
            font_size: "20sp"
            bold: True
            color: 1, 1, 1, 1
            halign: "right"
            valign: "middle"
            text_size: self.size

    # أزرار الوظائف
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "52dp"
        spacing: "2dp"

        Button:
            text: root.txt_btn_import
            font_name: root.font_name
            font_size: "15sp"
            bold: True
            background_normal: ""
            background_color: 0.12, 0.18, 0.26, 1
            on_release: root.open_file_selector()

        Button:
            text: root.txt_btn_log
            font_name: root.font_name
            font_size: "15sp"
            bold: True
            background_normal: ""
            background_color: 0.12, 0.18, 0.26, 1
            on_release: root.show_targets_log()

    # مساحة العرض المركزية
    BoxLayout:
        id: content_area
        orientation: "vertical"
        padding: "16dp"
        spacing: "12dp"

        Label:
            id: info_display
            text: root.txt_main_info
            font_name: root.font_name
            font_size: "16sp"
            color: 0.75, 0.82, 0.9, 1
            halign: "center"
            valign: "middle"
            text_size: self.size
'''

def get_hwid():
    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Secure = autoclass('android.provider.Settings$Secure')
            context = PythonActivity.mActivity.getContentResolver()
            aid = Secure.getString(context, Secure.ANDROID_ID)
            if aid:
                return str(aid)[:12].upper()
        except Exception:
            pass
    return str(uuid.getnode())[:12].upper()


class MainLayout(BoxLayout):
    font_name = StringProperty(APP_FONT)
    target_count = NumericProperty(0)
    
    txt_app_title = StringProperty("")
    txt_header_status = StringProperty("")
    txt_btn_import = StringProperty("")
    txt_btn_log = StringProperty("")
    txt_main_info = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raw_targets = []
        self.update_arabic_texts()

    def update_arabic_texts(self, exp_date=""):
        self.txt_app_title = ar("القناص PRO 🎯")
        status_word = ar("مفعل وجاهز") if exp_date else ar("جاري التحقق")
        self.txt_header_status = f"{ar('الأهداف')}: {self.target_count} | {status_word}"
        self.txt_btn_import = ar("استيراد مشفر (Excel/CSV)")
        self.txt_btn_log = ar("سجل الأهداف")
        
        if exp_date:
            self.txt_main_info = (
                f"{ar('مرحباً بك في القناص PRO')}\n"
                f"{ar('الترخيص سارٍ حتى:')} {exp_date}\n\n"
                f"{ar('اضغط على زر (استيراد مشفر) لاختيار ملف البيانات للبدء.')}"
            )
        else:
            self.txt_main_info = ar("يرجى تفعيل التطبيق للبدء")

    def open_file_selector(self):
        """فتح نافذة اختيار ملفات Excel / CSV تفاعلية"""
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # مسار التخزين الافتراضي
        start_path = "/sdcard" if platform == "android" else os.path.expanduser("~")
        
        chooser = FileChooserListView(
            path=start_path,
            filters=["*.csv", "*.xlsx", "*.xls", "*.txt"],
            size_hint_y=0.85
        )
        layout.add_widget(chooser)
        
        btn_bar = BoxLayout(size_hint_y=0.15, spacing=10)
        btn_cancel = Button(text=ar("إلغاء"), font_name=APP_FONT)
        btn_select = Button(text=ar("تحميل الملف"), font_name=APP_FONT, background_color=(0.1, 0.7, 0.3, 1))
        
        btn_bar.add_widget(btn_cancel)
        btn_bar.add_widget(btn_select)
        layout.add_widget(btn_bar)

        popup = Popup(
            title=ar("اختر ملف الأهداف (Excel أو CSV)"),
            title_font=APP_FONT,
            content=layout,
            size_hint=(0.95, 0.85),
            auto_dismiss=False
        )

        def do_load(instance):
            if chooser.selection:
                selected_file = chooser.selection[0]
                popup.dismiss()
                self.process_imported_file(selected_file)

        btn_select.bind(on_release=do_load)
        btn_cancel.bind(on_release=popup.dismiss)
        popup.open()

    def process_imported_file(self, filepath):
        """قراءة الملف المحمّل وعد الأهداف بداخله"""
        try:
            filename = os.path.basename(filepath)
            count = 0
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.strip() for line in f if line.strip()]
                count = len(lines)
                self.raw_targets = lines[:200]  # حفظ عينة

            self.target_count = count
            self.txt_header_status = f"{ar('الأهداف')}: {self.target_count} | {ar('تم التحميل')}"
            self.ids.info_display.text = (
                f"{ar('تم تحميل الملف بنجاح:')}\n{filename}\n\n"
                f"{ar('عدد الأهداف المسجلة:')} {count}\n"
                f"{ar('اضغط على (سجل الأهداف) لاستعراض القائمة.')}"
            )
        except Exception as e:
            self.ids.info_display.text = f"{ar('خطأ في قراءة الملف:')}\n{str(e)}"

    def show_targets_log(self):
        """استعراض سجل الأهداف المحملة"""
        if not self.raw_targets:
            msg = ar("سجل الأهداف فارغ حالياً. قم باستيراد ملف أولاً.")
        else:
            preview = "\n".join(self.raw_targets[:15])
            msg = f"{ar('سجل الأهداف (أول 15 عنصر):')}\n\n{preview}"

        box = BoxLayout(orientation='vertical', padding=12, spacing=10)
        lbl = Label(text=msg, font_name=APP_FONT, halign='center', valign='middle')
        lbl.bind(size=lbl.setter('text_size'))
        box.add_widget(lbl)
        
        btn_close = Button(text=ar("إغلاق"), font_name=APP_FONT, size_hint_y=0.2)
        box.add_widget(btn_close)
        
        p = Popup(title=ar("سجل الأهداف"), title_font=APP_FONT, content=box, size_hint=(0.9, 0.7))
        btn_close.bind(on_release=p.dismiss)
        p.open()

    def unlock_app(self, exp_date):
        self.update_arabic_texts(exp_date=str(exp_date))


class AlknasApp(App):
    def build(self):
        Builder.load_string(KV)
        self.root_layout = MainLayout()
        return self.root_layout

    def on_start(self):
        # التحقق من وجود ملف التفعيل الساري
        if os.path.exists(LICENSE_FILE):
            try:
                with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                    saved_key = f.read().strip().upper()
                dev_id, exp_str, sig = saved_key.split("-")
                if dev_id == get_hwid():
                    raw_token = f"{SALT}{dev_id}{exp_str}"
                    if sig == hashlib.sha256(raw_token.encode('utf-8')).hexdigest().upper()[:8]:
                        exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
                        if datetime.now().date() <= exp_date:
                            self.root_layout.unlock_app(exp_date)
            except Exception:
                pass

if __name__ == "__main__":
    AlknasApp().run()
