from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.core.text import LabelBase
import os

# محاولة آمنة جداً لاستيراد مكتبة تعديل الحروف دون التسبب في انهيار التطبيق
HAS_ARABIC_FIX = False
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_FIX = True
except ImportError:
    pass

def arabic_text(text):
    """دالة آمنة لمعالجة النصوص العربية"""
    if HAS_ARABIC_FIX:
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            return get_display(reshaped_text)
        except:
            return text
    return text

# التحقق من وجود ملف الخط في المستودع لضمان عدم حدوث خطأ
font_path = 'font.ttf'
if os.path.exists(font_path):
    try:
        LabelBase.register(name='ArabicFont', fn_regular=font_path)
    except Exception as e:
        print(f"خطأ في تسجيل الخط: {e}")

class AlknasApp(App):
    def build(self):
        root_layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # اختيار الخط الافتراضي إن لم يتوفر ملف الخط لتجنب الانهيار
        current_font = 'ArabicFont' if os.path.exists(font_path) else 'Roboto'
        
        self.header_label = Label(
            text=arabic_text("تطبيق القناص - النسخة المستقرة"), 
            font_name=current_font,
            font_size=20, 
            size_hint=(1, 0.2)
        )
        root_layout.add_widget(self.header_label)
        
        self.info_label = Label(
            text=arabic_text("الحالة: يعمل بثبات تام بدون إغلاق"),
            font_name=current_font,
            font_size=16,
            size_hint=(1, 0.2)
        )
        root_layout.add_widget(self.info_label)
        
        btn = Button(
            text=arabic_text("اختبار عمل التطبيق"), 
            font_name=current_font,
            size_hint=(1, 0.2)
        )
        btn.bind(on_press=self.on_btn_click)
        root_layout.add_widget(btn)
        
        self.log_input = TextInput(
            text=arabic_text("--- تم فتح التطبيق بنجاح وثبات تام ---\n"),
            font_name=current_font,
            readonly=True,
            size_hint=(1, 0.4)
        )
        root_layout.add_widget(self.log_input)
        
        return root_layout

    def on_btn_click(self, instance):
        self.log_input.text += "\n" + arabic_text("تم النقر والتعامل مع الواجهة بنجاح!")

if __name__ == '__main__':
    AlknasApp().run()
