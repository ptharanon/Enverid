from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivymd.uix.label import MDLabel

class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", spacing=10, padding=10)
        root.add_widget(MDLabel(text="Settings (coming soon)", halign="center"))
        self.add_widget(root)
