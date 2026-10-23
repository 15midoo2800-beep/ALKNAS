from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
import os

class AlknasApp(App):
    def build(self):
        root_layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        self.header_label = Label(
            text="تطبيق القناص - النسخة المستقرة", 
            font_size=20, 
            size_hint=(1, 0.2)
        )
        root_layout.add_widget(self.header_label)
        
        self.info_label = Label(
            text="الحالة: يعمل بثبات تام بدون إغلاق فجائي",
            font_size=16,
            size_hint=(1, 0.2)
        )
        root_layout.add_widget(self.info_label)
        
        btn = Button(text="اختبار عمل التطبيق", size_hint=(1, 0.2))
        btn.bind(on_press=self.on_btn_click)
        root_layout.add_widget(btn)
        
        self.log_input = TextInput(
            text="--- تم فتح التطبيق بنجاح وثبات ---\n",
            readonly=True,
            size_hint=(1, 0.4)
        )
        root_layout.add_widget(self.log_input)
        
        return root_layout

    def on_btn_click(self, instance):
        self.log_input.text += "\nتم النقر والتعامل مع الواجهة بنجاح!"

if __name__ == '__main__':
    AlknasApp().run()
