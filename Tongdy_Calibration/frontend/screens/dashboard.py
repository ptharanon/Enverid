from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp, sp
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import ObjectProperty

from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRectangleFlatButton

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import time
from kivy.core.window import Window

from backend.ui_queue import ui_queue

MAX_TIME_WINDOW = 300  # seconds

class GraphImage(Image):
    """Custom Image widget for touch detection on Matplotlib graph."""
    dashboard = ObjectProperty(None)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Convert touch to local coordinates
            local_x = (touch.x - self.x) / self.width

            if not self.dashboard.time_data_1 and not self.dashboard.time_data_2:
                return super().on_touch_down(touch)

            # Compute approximate time from relative x
            all_times = self.dashboard.time_data_1 + self.dashboard.time_data_2
            min_time, max_time = min(all_times), max(all_times)
            touch_time = min_time + local_x * (max_time - min_time)

            # Find nearest data point from sensor1
            nearest_1 = min(
                zip(self.dashboard.time_data_1, self.dashboard.co2_data_1),
                key=lambda t: abs(t[0] - touch_time),
                default=(None,None)
            )
            # Find nearest data point from sensor2
            nearest_2 = min(
                zip(self.dashboard.time_data_2, self.dashboard.co2_data_2),
                key=lambda t: abs(t[0] - touch_time),
                default=(None,None)
            )

            msg = ""
            if nearest_1[0] is not None:
                msg += f"Sensor 1\nTime: {nearest_1[0]:.1f}s\nCO₂: {nearest_1[1]:.0f} ppm\n\n"
            if nearest_2[0] is not None:
                msg += f"Sensor 2\nTime: {nearest_2[0]:.1f}s\nCO₂: {nearest_2[1]:.0f} ppm"

            if msg:
                popup = Popup(title="Data Point",
                              content=Label(text=msg),
                              size_hint=(None,None),
                              size=(dp(200), dp(180)))
                popup.open()
            return True
        return super().on_touch_down(touch)

class DashboardScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller

        self.scale = Window.height / 480.0

        app = MDApp.get_running_app()
        self.theme_cls = app.theme_cls

        # Track graph data
        self.start_time = time.time()
        self.time_data_1, self.co2_data_1 = [], []
        self.time_data_2, self.co2_data_2 = [], []

        # ---------------- Scrollable Root ----------------
        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12*self.scale),
            padding=dp(12*self.scale),
            adaptive_height=True
        )
        scroll.add_widget(content)
        self.add_widget(scroll)

        # ---------------- Status Card ----------------
        status_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(50*self.scale),
            padding=dp(8*self.scale),
            radius=[12]*4,
            md_bg_color=self.theme_cls.bg_light
        )
        self.status_label = MDLabel(
            text="Status: Idle",
            font_size=sp(16*self.scale),
            halign="center",
            theme_text_color="Primary"
        )
        status_card.add_widget(self.status_label)
        content.add_widget(status_card)

        # ---------------- Graph Card ----------------
        graph_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(220*self.scale),
            padding=dp(6*self.scale),
            radius=[12]*4,
            md_bg_color=self.theme_cls.bg_light
        )

        self.fig, self.ax = plt.subplots(figsize=(6,3))
        self.line1, = self.ax.plot([], [], color='red', marker='o', label='Sensor 1')
        self.line2, = self.ax.plot([], [], color='blue', marker='o', label='Sensor 2')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CO₂ (ppm)")
        self.ax.set_xlim(0, 60)
        self.ax.set_ylim(0, 2000)
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()

        self.graph_widget = GraphImage(size_hint=(1,1))
        self.graph_widget.dashboard = self
        graph_card.add_widget(self.graph_widget)
        content.add_widget(graph_card)

        # ---------------- Live Readings ----------------
        live_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(150 * self.scale),
            padding=dp(6 * self.scale),
            radius=[12, 12, 12, 12],
            md_bg_color=self.theme_cls.bg_light,
        )
        live_card.add_widget(MDLabel(text="Live Readings", halign="center", font_style="H6"))

        live_layout = GridLayout(
            cols=2, 
            spacing=dp(40 * self.scale), 
            size_hint_y=None,
            padding=[dp(40 * self.scale), 0]
        )
        live_layout.bind(minimum_height=live_layout.setter("height"))

        def build_sensor_live(title):
            layout = MDBoxLayout(orientation="vertical", spacing=dp(4 * self.scale),
                                 size_hint_x=None, width=dp(220 * self.scale))
            layout.add_widget(MDLabel(text=f"[b]{title}[/b]", markup=True, halign="center", font_size="18sp"))
            grid = GridLayout(cols=2, spacing=dp(6 * self.scale))
            lbl_co2 = MDLabel(text="CO²:", halign="right")
            val_co2 = MDLabel(text="-- ppm", halign="left")
            lbl_temp = MDLabel(text="Temp:", halign="right")
            val_temp = MDLabel(text="-- °C", halign="left")
            lbl_rh = MDLabel(text="RH:", halign="right")
            val_rh = MDLabel(text="-- %", halign="left")
            grid.add_widget(lbl_co2); grid.add_widget(val_co2)
            grid.add_widget(lbl_temp); grid.add_widget(val_temp)
            grid.add_widget(lbl_rh); grid.add_widget(val_rh)
            layout.add_widget(grid)
            return layout, val_co2, val_temp, val_rh

        sensor1_live, self.lbl1_co2, self.lbl1_temp, self.lbl1_rh = build_sensor_live("Sensor 1 Live")
        sensor2_live, self.lbl2_co2, self.lbl2_temp, self.lbl2_rh = build_sensor_live("Sensor 2 Live")

        live_layout.add_widget(sensor1_live)
        live_layout.add_widget(sensor2_live)
        live_card.add_widget(live_layout)
        content.add_widget(live_card)

        # ---------------- Calibration Card ----------------
        calib_card = MDCard(
            orientation="vertical",
            padding=dp(10*self.scale),
            size_hint=(1, None),
            height=dp(180*self.scale),
            radius=[12]*4,
            md_bg_color=self.theme_cls.bg_light
        )
        calib_card.add_widget(MDLabel(text="Calibration Averages (CO²)", halign="center", font_style="H6"))
        calib_layout = GridLayout(
            cols=2,
            spacing=dp(40 * self.scale),
            padding=[dp(40 * self.scale), 0],
            size_hint_y=None,
        )
        calib_layout.bind(minimum_height=calib_layout.setter("height"))

        def build_sensor_calib(title):
            layout = MDBoxLayout(orientation="vertical", spacing=dp(4 * self.scale),
                                 size_hint_x=None, width=dp(220 * self.scale))
            layout.add_widget(MDLabel(text=f"[b]{title}[/b]", markup=True, halign="center", font_size="18sp"))
            grid = GridLayout(cols=2, spacing=dp(6 * self.scale))
            lbl_base = MDLabel(text="Baseline:", halign="right")
            val_base = MDLabel(text="--", halign="left")
            lbl_exp = MDLabel(text="Exposure:", halign="right")
            val_exp = MDLabel(text="--", halign="left")
            lbl_vent = MDLabel(text="Post-vent:", halign="right")
            val_vent = MDLabel(text="--", halign="left")
            grid.add_widget(lbl_base); grid.add_widget(val_base)
            grid.add_widget(lbl_exp); grid.add_widget(val_exp)
            grid.add_widget(lbl_vent); grid.add_widget(val_vent)
            layout.add_widget(grid)
            return layout, val_base, val_exp, val_vent

        sensor1_calib, self.lbl1_baseline, self.lbl1_exposure, self.lbl1_vented = build_sensor_calib("Sensor 1 Calibration")
        sensor2_calib, self.lbl2_baseline, self.lbl2_exposure, self.lbl2_vented = build_sensor_calib("Sensor 2 Calibration")

        calib_layout.add_widget(sensor1_calib)
        calib_layout.add_widget(sensor2_calib)
        calib_card.add_widget(calib_layout)
        content.add_widget(calib_card)

        # ---------------- Buttons ----------------
        btn_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(70*self.scale), spacing=dp(20*self.scale))
        btn_row.add_widget(MDRectangleFlatButton(text="Start", on_release=self.on_start))
        btn_row.add_widget(MDRectangleFlatButton(text="Stop", on_release=self.on_stop))
        content.add_widget(btn_row)

        # Schedule UI refresh
        Clock.schedule_interval(self._drain_ui_queue, 1)

    # ---------------- Controller ----------------
    def on_start(self, *_):
        if not self.controller.running:
            self.controller.start()

    def on_stop(self, *_):
        if self.controller.running:
            self.controller.stop()
            self.status_label.text = "Status: Stopping..."

    # ---------------- Update Graph ----------------
    def _update_graph_image(self):
        self.ax.clear()
        self.ax.plot(self.time_data_1, self.co2_data_1, color='red', marker='o', label='Sensor 1')
        self.ax.plot(self.time_data_2, self.co2_data_2, color='blue', marker='o', label='Sensor 2')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CO₂ (ppm)")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        all_times = self.time_data_1 + self.time_data_2
        if all_times:
            min_time = min(all_times)
            max_time = max(all_times)
            if max_time - min_time < MAX_TIME_WINDOW:
                max_time = min_time + MAX_TIME_WINDOW
            self.ax.set_xlim(min_time, max_time)
        else:
            self.ax.set_xlim(0, MAX_TIME_WINDOW)
        self.ax.set_ylim(0, 2000)

        buf = io.BytesIO()
        self.fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        self.graph_widget.texture = CoreImage(buf, ext='png').texture
        buf.close()

    # ---------------- UI Queue Handler ----------------
    def _drain_ui_queue(self, dt):
        while not ui_queue.empty():
            msg = ui_queue.get()
            t = msg.get("type")

            if t == "status":
                self.status_label.text = f"Status: {msg['text']}"

            # Obsolete ???
            elif t == "sensor_value":
                val = msg.get("value")
                if val is not None:
                    self.lbl1_co2.text = f"CO₂: {val:.0f} ppm"

            elif t == "live_values":
                data = msg.get("data", {})
                sensor_id = data.get("sensor_id", 1)
                co2 = data.get("co2")
                temp = data.get("temperature")
                rh = data.get("humidity")
                elapsed = time.time() - self.start_time

                if sensor_id == 1:
                    if co2 is not None:
                        self.lbl1_co2.text = f"{co2:.0f} ppm"
                        self.time_data_1.append(elapsed)
                        self.co2_data_1.append(co2)
                        while self.time_data_1 and (elapsed - self.time_data_1[0] > MAX_TIME_WINDOW):
                            self.time_data_1.pop(0)
                            self.co2_data_1.pop(0)
                    if temp is not None: self.lbl1_temp.text = f"{temp:.1f} °C"
                    if rh is not None: self.lbl1_rh.text = f"{rh:.1f} %"
                else:
                    if co2 is not None:
                        self.lbl2_co2.text = f"{co2:.0f} ppm"
                        self.time_data_2.append(elapsed)
                        self.co2_data_2.append(co2)
                        while self.time_data_2 and (elapsed - self.time_data_2[0] > MAX_TIME_WINDOW):
                            self.time_data_2.pop(0)
                            self.co2_data_2.pop(0)
                    if temp is not None: self.lbl2_temp.text = f"{temp:.1f} °C"
                    if rh is not None: self.lbl2_rh.text = f"{rh:.1f} %"

                self._update_graph_image()

            elif t == "struct_update":
                s = msg["struct"]
                print("Struct update:", s)

                for sid, val in s.items():
                    print(f"  Sensor {sid}: {val}")
                    baseline_val = "--" if val['baseline'] is None else f"{val['baseline']:.2f}"
                    exposure_val = "--" if val['exposure'] is None else f"{val['exposure']:.2f}"
                    vented_val = "--" if val['vented'] is None else f"{val['vented']:.2f}"

                    if sid == 1:
                        self.lbl1_baseline.text = f"{baseline_val} ppm"
                        self.lbl1_exposure.text = f"{exposure_val} ppm"
                        self.lbl1_vented.text = f"{vented_val} ppm"
                    else:
                        self.lbl2_baseline.text = f"{baseline_val} ppm"
                        self.lbl2_exposure.text = f"{exposure_val} ppm"
                        self.lbl2_vented.text = f"{vented_val} ppm"