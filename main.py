import os
import uuid
import base64
import hmac
import hashlib
from datetime import datetime
import webbrowser
import urllib.parse

from kivy.core.text import LabelBase
from kivy.core.clipboard import Clipboard
from kivy.utils import platform
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import Snackbar

# تسجيل الخط العربي إن وجد
if os.path.exists("font.ttf"):
    LabelBase.register(name="AppFont", fn_regular="font.ttf")
    DEFAULT_FONT = "AppFont"
else:
    DEFAULT_FONT = "Roboto"

KV = '''
<ActivationScreen>:
    name: "activation"
    canvas.before:
        Color:
            rgba: 0.06, 0.08, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size

    ScrollView:
        do_scroll_x: False
        do_scroll_y: True

        BoxLayout:
            orientation: "vertical"
            padding: ["22dp", "28dp", "22dp", "30dp"]
            spacing: "18dp"
            size_hint_y: None
            height: self.minimum_height

            # العنوان والشعار
            BoxLayout:
                orientation: "vertical"
                spacing: "6dp"
                size_hint_y: None
                height: "80dp"

                MDLabel:
                    text: "🛡️ تفعيل التطبيق"
                    font_name: root.app_font
                    font_size: "30sp"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.2, 0.85, 0.55, 1

                MDLabel:
                    text: "يرجى إدخال مفتاح الترخيص أو طلب التفعيل"
                    font_name: root.app_font
                    font_size: "16sp"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.65, 0.72, 0.82, 1

            # بطاقة كود الجهاز
            MDCard:
                orientation: "vertical"
                padding: ["18dp", "16dp", "18dp", "16dp"]
                spacing: "12dp"
                radius: [18, 18, 18, 18]
                elevation: 4
                md_bg_color: 0.12, 0.16, 0.23, 1
                size_hint_y: None
                height: "155dp"

                MDLabel:
                    text: "كود الجهاز الخاص بك (Device ID):"
                    font_name: root.app_font
                    font_size: "17sp"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: 0.85, 0.88, 0.92, 1
                    size_hint_y: None
                    height: "26dp"

                BoxLayout:
                    orientation: "horizontal"
                    spacing: "12dp"
                    size_hint_y: None
                    height: "55dp"

                    MDLabel:
                        id: device_id_label
                        text: root.device_id
                        font_size: "22sp"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: 0.25, 0.88, 0.55, 1
                        valign: "middle"

                    MDRaisedButton:
                        text: "نسخ الكود 📋"
                        font_name: root.app_font
                        font_size: "17sp"
                        bold: True
                        size_hint_y: 1
                        md_bg_color: 0.2, 0.55, 0.85, 1
                        on_release: root.copy_device_code()

            # بطاقة إدخال المفتاح وتأكيده
            MDCard:
                orientation: "vertical"
                padding: ["18dp", "18dp", "18dp", "18dp"]
                spacing: "14dp"
                radius: [18, 18, 18, 18]
                elevation: 4
                md_bg_color: 0.12, 0.16, 0.23, 1
                size_hint_y: None
                height: "190dp"

                MDTextField:
                    id: key_input
                    hint_text: "أدخل كود التفعيل هنا"
                    font_name_hint_text: root.app_font
                    font_size: "19sp"
                    mode: "rectangle"
                    line_color_focus: 0.25, 0.88, 0.55, 1
                    hint_text_color_normal: 0.65, 0.7, 0.78, 1
                    text_color_normal: 1, 1, 1, 1

                MDRaisedButton:
                    text: "تأكيد وتفعيل التطبيق 🚀"
                    font_name: root.app_font
                    font_size: "19sp"
                    bold: True
                    size_hint_x: 1
                    height: "54dp"
                    md_bg_color: 0.18, 0.78, 0.44, 1
                    on_release: root.verify_license()

            # بطاقة شراء الاشتراك
            MDCard:
                orientation: "vertical"
                padding: ["18dp", "18dp", "18dp", "18dp"]
                spacing: "14dp"
                radius: [18, 18, 18, 18]
                elevation: 4
                md_bg_color: 0.1, 0.13, 0.19, 1
                size_hint_y: None
                height: "205dp"

                MDLabel:
                    text: "طلب تفعيل جديد:"
                    font_name: root.app_font
                    font_size: "19sp"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    size_hint_y: None
                    height: "28dp"

                MDRaisedButton:
                    id: duration_btn
                    text: "مدة الاشتراك: شهر واحد ▼"
                    font_name: root.app_font
                    font_size: "18sp"
                    bold: True
                    size_hint_x: 1
                    height: "50dp"
                    md_bg_color: 0.2, 0.26, 0.36, 1
                    on_release: root.open_duration_menu()

                MDRaisedButton:
                    text: "إرسال طلب التفعيل عبر واتساب 💬"
                    font_name: root.app_font
                    font_size: "18sp"
                    bold: True
                    size_hint_x: 1
                    height: "52dp"
                    md_bg_color: 0.15, 0.68, 0.37, 1
                    on_release: root.send_to_whatsapp()

            # زر التواصل السريع مع الإدارة
            MDRaisedButton:
                text: "تواصل مع الإدارة مباشرة 📞"
                font_name: root.app_font
                font_size: "18sp"
                bold: True
                size_hint_x: 1
                height: "54dp"
                md_bg_color: 0.12, 0.45, 0.28, 1
                on_release: root.contact_admin()
'''

class ActivationScreen(Screen):
    WHATSAPP_NUMBER = "201155661920"
    app_font = DEFAULT_FONT
    SECRET_KEY = b"ALKNAS_SECURE_KEY_2026_PRO"

    def __init__(self, **kwargs):
        self.device_id = self.get_unique_device_id()
        self.selected_duration = "شهر واحد"
        super().__init__(**kwargs)
        self.menu = None

    def get_unique_device_id(self):
        if platform == "android":
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Secure = autoclass('android.provider.Settings$Secure')
                context = PythonActivity.mActivity.getContentResolver()
                android_id = Secure.getString(context, Secure.ANDROID_ID)
                if android_id:
                    return str(android_id)[:10].upper()
            except Exception:
                pass
        return str(uuid.getnode())[:10].upper()

    def on_kv_post(self, base_widget):
        durations = ["شهر واحد", "3 أشهر", "6 أشهر", "سنة كاملة"]
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": dur,
                "font_name": self.app_font,
                "on_release": lambda x=dur: self.set_duration(x),
            } for dur in durations
        ]
        self.menu = MDDropdownMenu(
            caller=self.ids.duration_btn,
            items=menu_items,
            width_mult=4,
        )

    def open_duration_menu(self):
        if self.menu:
            self.menu.open()

    def set_duration(self, text_item):
        self.selected_duration = text_item
        self.ids.duration_btn.text = f"مدة الاشتراك: {text_item} ▼"
        self.menu.dismiss()

    def copy_device_code(self):
        Clipboard.copy(self.device_id)
        Snackbar(
            text="تم نسخ كود الجهاز بنجاح! ✅",
            font_size="17sp",
            duration=2
        ).open()

    def _open_whatsapp(self, message):
        encoded_msg = urllib.parse.quote(message)
        if platform == "android":
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')

                url = f"https://api.whatsapp.com/send?phone={self.WHATSAPP_NUMBER}&text={encoded_msg}"
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(url))
                PythonActivity.mActivity.startActivity(intent)
                return
            except Exception:
                pass

        web_url = f"https://wa.me/{self.WHATSAPP_NUMBER}?text={encoded_msg}"
        webbrowser.open(web_url)

    def send_to_whatsapp(self):
        msg = (
            f"مرحباً، أود شراء تفعيل لتطبيق القناص.\n"
            f"📱 كود جهازي: {self.device_id}\n"
            f"⏳ مدة الاشتراك المطلوبة: {self.selected_duration}"
        )
        self._open_whatsapp(msg)

    def contact_admin(self):
        msg = (
            f"مرحباً إدارة تطبيق القناص، أود الاستفسار والتواصل بخصوص التفعيل.\n"
            f"📱 كود جهازي: {self.device_id}"
        )
        self._open_whatsapp(msg)

    def verify_license(self):
        entered_key = self.ids.key_input.text.strip()
        if not entered_key:
            Snackbar(text="يرجى إدخال كود التفعيل أولاً", font_size="16sp").open()
            return

        # فحص المفتاح المشفر
        try:
            decoded = base64.b64decode(entered_key.encode('utf-8')).decode('utf-8')
            parts = decoded.split("|")
            if len(parts) != 3:
                raise ValueError("Format error")

            dev_id, expiry_str, signature = parts

            # 1. التحقق من تطابق كود الجهاز
            if dev_id.upper() != self.device_id:
                Snackbar(text="❌ هذا الكود مخصص لجهاز آخر!", font_size="16sp").open()
                return

            # 2. التحقق من التوقيع الرقمي لمنع التزوير
            expected_sig = hmac.new(
                self.SECRET_KEY,
                f"{dev_id}|{expiry_str}".encode('utf-8'),
                hashlib.sha256
            ).hexdigest()[:12]

            if signature != expected_sig:
                Snackbar(text="❌ كود تفعيل غير صالح أو مزور!", font_size="16sp").open()
                return

            # 3. التحقق من الصلاحية والتاريخ
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            if datetime.now() > expiry_date:
                Snackbar(text=f"⚠️ انتهت صلاحية هذا الكود في ({expiry_str})", font_size="16sp").open()
                return

            Snackbar(
                text=f"✅ تم التفعيل بنجاح! صالح حتى: {expiry_str}",
                font_size="17sp",
                duration=3
            ).open()

        except Exception:
            Snackbar(text="❌ كود التفعيل غير صالح، يرجى التأكد منه", font_size="16sp").open()


class MainApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        Builder.load_string(KV)
        return ActivationScreen()

if __name__ == "__main__":
    MainApp().run()
