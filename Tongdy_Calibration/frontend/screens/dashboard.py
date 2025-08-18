from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from backend.ui_queue import ui_queue

class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.sensor_cards = {}  # {sensor_id: MDCard}
        self.sensor_labels = {}  # {sensor_id: MDLabel}

        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        self.add_widget(layout)

        for sensor_id in [1,2,3]:
            card = MDCard(orientation="vertical", padding=10, size_hint=(1, None), height=80, md_bg_color=(0.1,0.1,0.2,1))
            label = MDLabel(text=f"Sensor {sensor_id}: --", halign="center", font_style="H5")
            card.add_widget(label)
            layout.add_widget(card)

            self.sensor_cards[sensor_id] = card
            self.sensor_labels[sensor_id] = label

        Clock.schedule_interval(self.update_ui, 0.5)

    def update_ui(self, dt):
        while not ui_queue.empty():
            sensor_id, value = ui_queue.get()
            if sensor_id in self.sensor_labels:
                label = self.sensor_labels[sensor_id]
                label.text = f"Sensor {sensor_id}: {value:.2f}"
                # Optional: change card color based on thresholds
                card = self.sensor_cards[sensor_id]
                if value > 1500:
                    card.md_bg_color = (1,0,0,1)  # red if high
                elif value > 800:
                    card.md_bg_color = (1,1,0,1)  # yellow if moderate
                else:
                    card.md_bg_color = (0.1,0.1,0.2,1)  # default
