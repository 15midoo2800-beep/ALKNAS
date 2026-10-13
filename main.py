import os
import uuid
import hashlib
from datetime import datetime
import urllib.parse
import webbrowser

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.core.clipboard import Clipboard
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.properties import StringProperty, NumericProperty

# تسجيل الخط العربي إن وجد
if os.path.exists("font.ttf"):
    LabelBase.register(name="AppFont", fn_regular="font.ttf")
    APP_FONT = "AppFont"
else:
    APP_FONT = "Roboto"

# المفتاح السري الموحد
SALT = "ALKNAS_PRO_SECURITY_2026"
LICENSE_FILE = "license.dat"
WHATSAPP_NUMBER = "201155661920"

KV = '''
<ActivationPopup>:
    size_hint: 0.9, 0.72
    auto_dismiss: False
    background_color: 0, 0, 0, 0.75

    BoxLayout:
        orientation: "vertical"
        padding: ["18dp", "20dp", "18dp", "20dp"]
        spacing: "12dp"
        canvas.before:
            Color:
                rgba: 0.14, 0.14, 0.14, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [8, 8, 8, 8]

        # العنوان
        Label:
            text: "تفعيل القناص"
            font_name: root.font_name
            font_size: "20sp"
            bold: True
            color: 1, 1, 1, 1
            size_hint_y: None
            height: "32dp"

        Widget:
            size_hint_y: None
            height: "1.5dp"
            canvas.before:
                Color:
                    rgba: 0.2, 0.65, 0.85, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

        Label:
            text: "نسخة تجارية مقفلة - مطلوب التفعيل"
            font_name: root.font_name
            font_size: "15sp"
            color: 0.85, 0.85, 0.85, 1
            size_hint_y: None
            height: "35dp"

        Widget:
            size_hint_y: 0.1

        # كود الجهاز
        Label:
            text: "كود جهازك (أرسله للإدارة):"
            font_name: root.font_name
            font_size: "16sp"
            color: 0.35, 0.68, 0.95, 1
            size_hint_y: None
            height: "26dp"

        Label:
            text: root.device_id
            font_size: "19sp"
            bold: True
            color: 0.35, 0.68, 0.95, 1
            size_hint_y: None
            height: "30dp"

        Widget:
            size_hint_y: 0.05

        # حقل إدخال الكود
        TextInput:
            id: key_input
            multiline: False
            halign: "center"
            font_size: "16sp"
            bold: True
            background_normal: ""
            background_color: 0.92, 0.93, 0.94, 1
            foreground_color: 0.1, 0.1, 0.1, 1
            padding: [10, 10, 10, 10]
            size_hint_y: None
            height: "44dp"

        # رسالة الخطأ أو النجاح
        Label:
            id: error_label
            text: root.status_message
            font_name: root.font_name
            font_size: "14sp"
            color: root.status_color
            size_hint_y: None
            height: "26dp"

        Widget:
            size_hint_y: 0.1

        # زر التفعيل الأخضر
        Button:
            text: "تفعيل الترخيص"
            font_name: root.font_name
            font_size: "17sp"
            bold: True
            background_normal: ""
            background_color: 0.05, 0.38, 0.15, 1
            size_hint_y: None
            height: "46dp"
            on_release: root.do_activate()

        # زر التواصل مع الإدارة
        Button:
            text: "تواصل مع الإدارة عبر واتساب"
            font_name: root.font_name
            font_size: "14sp"
            background_normal: ""
            background_color: 0.12, 0.22, 0.32, 1
            size_hint_y: None
            height: "36dp"
            on_release: root.contact_admin()


<MainLayout>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: 0.02, 0.03, 0.05, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # الشريط العلوي
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "55dp"
        padding: ["16dp", "0dp", "16dp", "0dp"]
        canvas.before:
            Color:
                rgba: 0.05, 0.07, 0.1, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: f"الأهداف: {root.target_count} | {root.app_status}"
            font_name: root.font_name
            font_size: "15sp"
            color: 0.18, 0.75, 0.35, 1
            halign: "left"
            valign: "middle"
            text_size: self.size

        Label:
            text: "القناص PRO 🎯"
            font_name: root.font_name
            font_size: "20sp"
            bold: True
            color: 0.85, 0.88, 0.92, 1
            halign: "right"
            valign: "middle"
            text_size: self.size

    # أزرار الوظائف العلوية
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "55dp"
        spacing: "1dp"
        canvas.before:
            Color:
                rgba: 0.12, 0.15, 0.2, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Button:
            text: "سجل الأهداف 📋"
            font_name: root.font_name
            font_size: "15sp"
            background_normal: ""
            background_color: 0.06, 0.08, 0.12, 1
            on_release: root.on_targets_log()

        Button:
            text: "استيراد مشفر (Excel/CSV) 📥"
            font_name: root.font_name
            font_size: "15sp"
            background_normal: ""
            background_color: 0.06, 0.08, 0.12, 1
            on_release: root.on_import_data()

    # مساحة العمل الرئيسية
    BoxLayout:
        orientation: "vertical"
        padding: "20dp"
        spacing: "15dp"

        Label:
            text: root.main_screen_info
            font_name: root.font_name
            font_size: "16sp"
            color: 0.6, 0.65, 0.75, 1
            halign: "center"
            valign: "middle"
            text_size: self.size
'''

def get_hwid():
    """استخراج كود الجهاز الحقيقي"""
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


class ActivationPopup(ModalView):
    device_id = StringProperty("")
    font_name = StringProperty(APP_FONT)
    status_message = StringProperty("")
    status_color = [0.95, 0.3, 0.3, 1]

    def __init__(self, main_widget, **kwargs):
        super().__init__(**kwargs)
        self.main_widget = main_widget
        self.device_id = get_hwid()

    def do_activate(self):
        entered_key = self.ids.key_input.text.strip().upper()
        if not entered_key:
            self.show_status("يرجى إدخال كود التفعيل", False)
            return

        parts = entered_key.split("-")
        # التنسيق القياسي المعتمد: كود_الجهاز-تاريخ_الانتهاء-التوقيع
        if len(parts) != 3:
            self.show_status("تنسيق المفتاح غير صحيح", False)
            return

        dev_id, exp_str, sig = parts

        # 1. مطابقة كود الجهاز
        if dev_id != self.device_id:
            self.show_status("هذا المفتاح مخصص لجهاز آخر", False)
            return

        # 2. مطابقة التوقيع الرقمي
        raw_token = f"{SALT}{dev_id}{exp_str}"
        expected_sig = hashlib.sha256(raw_token.encode('utf-8')).hexdigest().upper()[:8]
        if sig != expected_sig:
            self.show_status("رمز التحقق غير مطابق", False)
            return

        # 3. فحص تاريخ الانتهاء
        try:
            exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
            if datetime.now().date() > exp_date:
                self.show_status(f"انتهت صلاحية المفتاح في ({exp_date})", False)
                return
        except ValueError:
            self.show_status("تنسيق التاريخ غير صحيح", False)
            return

        # حفظ ملف الترخيص محلياً
        try:
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                f.write(entered_key)
        except Exception:
            pass

        self.show_status("تم التفعيل بنجاح! جاري الفتح...", True)
        self.main_widget.unlock_app(exp_date)
        self.dismiss()

    def show_status(self, msg, is_success):
        self.status_message = msg
        self.status_color = [0.2, 0.85, 0.4, 1] if is_success else [0.95, 0.3, 0.3, 1]

    def contact_admin(self):
        msg = f"مرحباً إدارة القناص، أود تفعيل التطبيق.\nكود جهازي: {self.device_id}"
        enc = urllib.parse.quote(msg)
        webbrowser.open(f"https://wa.me/{WHATSAPP_NUMBER}?text={enc}")


class MainLayout(BoxLayout):
    font_name = StringProperty(APP_FONT)
    target_count = NumericProperty(0)
    app_status = StringProperty("جاري التحقق")
    main_screen_info = StringProperty("يرجى تفعيل التطخيص للبدء")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = None

    def on_start_check(self):
        """فحص حالة التفعيل عند فتح التطبيق"""
        if self.check_existing_license():
            return
        # إظهار نافذة التفعيل إذا لم يكن مفعلاً
        self.popup = ActivationPopup(main_widget=self)
        self.popup.open()

    def check_existing_license(self):
        if not os.path.exists(LICENSE_FILE):
            return False
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                saved_key = f.read().strip().upper()
            dev_id, exp_str, sig = saved_key.split("-")
            if dev_id == get_hwid():
                raw_token = f"{SALT}{dev_id}{exp_str}"
                if sig == hashlib.sha256(raw_token.encode('utf-8')).hexdigest().upper()[:8]:
                    exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
                    if datetime.now().date() <= exp_date:
                        self.unlock_app(exp_date)
                        return True
        except Exception:
            pass
        return False

    def unlock_app(self, exp_date):
        self.app_status = "مفعل وجاهز"
        self.main_screen_info = f"مرحباً بك في القناص PRO\nالاشتراك سارٍ حتى: {exp_date}\nجاهز لاستيراد الأهداف ومطابقة اللوحات."

    def on_import_data(self):
        if self.app_status == "جاري التحقق":
            if self.popup:
                self.popup.open()
            return
        # كود استيراد البيانات
        pass

    def on_targets_log(self):
        if self.app_status == "جاري التحقق":
            if self.popup:
                self.popup.open()
            return
        # كود عرض السجل
        pass


class AlknasApp(App):
    def build(self):
        Builder.load_string(KV)
        root = MainLayout()
        return root

    def on_start(self):
        self.root.on_start_check()

if __name__ == "__main__":
    AlknasApp().run()
