from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.card import MDCard
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from backend.ui_queue import ui_queue

class DashboardScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller

        root = BoxLayout(orientation="vertical", spacing=10, padding=10)
        self.add_widget(root)

        # Status
        self.status_label = MDLabel(text="Status: Ready", halign="center", font_style="H6")
        root.add_widget(self.status_label)

        # OLD - OBSOLETE
        # Live sensor
        # live = MDCard(orientation="vertical", padding=10, size_hint=(1, None), height=120)
        # live.add_widget(MDLabel(text="Real-time CO2 (ppm)", halign="center", font_style="H6"))
        # self.live_value = MDLabel(text="--", halign="center", font_style="H4")
        # live.add_widget(self.live_value)
        # root.add_widget(live)

        # Struct values
        # card = MDCard(orientation="vertical", padding=10, size_hint=(1, None), height=180)
        # card.add_widget(MDLabel(text="CO2 Average", halign="center", font_style="H6"))
        # grid = GridLayout(cols=3, height=100, size_hint=(1, None), padding=10, spacing=10)
        # self.baseline = MDLabel(text="Baseline:\n--", halign="center")
        # self.exposure = MDLabel(text="Exposure:\n--", halign="center")
        # self.vented = MDLabel(text="Post-vent:\n--", halign="center")
        # for w in (self.baseline, self.exposure, self.vented):
        #     grid.add_widget(w)
        # card.add_widget(grid)
        # root.add_widget(card)


        # Live values (CO2 / Temp / RH)
        live = MDCard(orientation="vertical", padding=10, size_hint=(1, None), height=160)
        live.add_widget(MDLabel(text="Live Readings", halign="center", font_style="H6"))
        grid_live = GridLayout(cols=3, size_hint=(1, None), height=80, padding=10, spacing=10)
        self.lbl_co2  = MDLabel(text="CO₂: -- ppm", halign="center")
        self.lbl_temp = MDLabel(text="Temp: -- °C", halign="center")
        self.lbl_rh   = MDLabel(text="RH: -- %", halign="center")
        for w in (self.lbl_co2, self.lbl_temp, self.lbl_rh):
            grid_live.add_widget(w)
        live.add_widget(grid_live)
        root.add_widget(live)

        # Struct values
        card = MDCard(orientation="vertical", padding=10, size_hint=(1, None), height=180)
        card.add_widget(MDLabel(text="Calibration Averages (CO₂)", halign="center", font_style="H6"))
        grid = GridLayout(cols=3, height=100, size_hint=(1, None), padding=10, spacing=10)
        self.baseline = MDLabel(text="Baseline:\n--", halign="center")
        self.exposure = MDLabel(text="Exposure:\n--", halign="center")
        self.vented   = MDLabel(text="Post-vent:\n--", halign="center")
        for w in (self.baseline, self.exposure, self.vented):
            grid.add_widget(w)
        card.add_widget(grid)
        root.add_widget(card)


        # Buttons
        btn_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=70, spacing=20, padding=[0,10,0,0])
        btn_row.add_widget(MDRectangleFlatButton(text="Start", on_release=self.on_start))
        btn_row.add_widget(MDRectangleFlatButton(text="Stop", on_release=self.on_stop))
        root.add_widget(btn_row)

        Clock.schedule_interval(self._drain_ui_queue, 0.5)

    def on_start(self, *_):
        if not self.controller.running:
            self.controller.start()

    def on_stop(self, *_):
        if self.controller.running:
            self.controller.stop()
            self.status_label.text = "Status: Stopping..."

    def _drain_ui_queue(self, dt):
        while not ui_queue.empty():
            msg = ui_queue.get()
            t = msg.get("type")
            if t == "status":
                self.status_label.text = f"Status: {msg['text']}"
            elif t == "sensor_value":
                # kept for backward-compat (single CO2 sample)
                val = msg.get("value")
                if val is not None:
                    self.lbl_co2.text = f"CO₂: {val:.0f} ppm"
            elif t == "live_values":
                data = msg.get("data", {})
                co2, temp, rh = data.get("co2"), data.get("temperature"), data.get("humidity")
                if co2  is not None: self.lbl_co2.text  = f"CO₂: {co2:.0f} ppm"
                if temp is not None: self.lbl_temp.text = f"Temp: {temp:.1f} °C"
                if rh   is not None: self.lbl_rh.text   = f"RH: {rh:.1f} %"
            elif t == "struct_update":
                s = msg["struct"]
                # self.baseline.text = "baseline"
                # self.exposure.text = "exposure"
                # self.vented.text = "vented"
                baseline_val = "--" if s['baseline'] is None else f"{s['baseline']:.2f}"
                exposure_val = "--" if s['exposure'] is None else f"{s['exposure']:.2f}"
                vented_val = "--" if s['vented'] is None else f"{s['vented']:.2f}"
                # Update labels with formatted values
                self.baseline.text = f"Baseline:\n{baseline_val}"
                self.exposure.text = f"Exposure:\n{exposure_val}"
                self.vented.text = f"Post-vent:\n{vented_val}"
