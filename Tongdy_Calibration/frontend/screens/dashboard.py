from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp, sp
from kivy.uix.popup import Popup
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

MAX_TIME_WINDOW = 600


class GraphImage(Image):
    """Custom Image widget for touch detection on Matplotlib graph."""
    dashboard = ObjectProperty(None)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Convert touch to local coordinates
            local_x = (touch.x - self.x) / self.width

            # Collect all time data from all sensors
            data_map = {
                1: (self.dashboard.time_data_1, self.dashboard.co2_data_1),
                2: (self.dashboard.time_data_2, self.dashboard.co2_data_2),
                3: (self.dashboard.time_data_3, self.dashboard.co2_data_3),
                4: (self.dashboard.time_data_4, self.dashboard.co2_data_4),
            }
            
            all_times = []
            for time_data, _ in data_map.values():
                all_times.extend(time_data)
            
            if not all_times:
                return super().on_touch_down(touch)

            # Compute approximate time from relative x
            min_time, max_time = min(all_times), max(all_times)
            touch_time = min_time + local_x * (max_time - min_time)

            # Find nearest data point from each sensor
            sensor_data_list = []
            for slot in range(1, 5):
                if slot in self.dashboard.slot_to_sensor_id:
                    sensor_id = self.dashboard.slot_to_sensor_id[slot]
                    time_data, co2_data = data_map[slot]
                    
                    if time_data:
                        nearest = min(
                            zip(time_data, co2_data),
                            key=lambda t: abs(t[0] - touch_time),
                            default=(None, None)
                        )
                        if nearest[0] is not None:
                            sensor_data_list.append({
                                'id': sensor_id,
                                'time': nearest[0],
                                'co2': nearest[1]
                            })

            if sensor_data_list:
                # Create a BoxLayout for the popup content
                content_layout = MDBoxLayout(
                    orientation='vertical',
                    spacing=dp(10),
                    padding=dp(15),
                    size_hint=(1, None)
                )
                
                # Calculate total height needed
                total_height = 0
                
                for sensor_info in sensor_data_list:
                    sensor_box = MDBoxLayout(
                        orientation='vertical',
                        spacing=dp(2),
                        size_hint_y=None,
                        height=dp(85)
                    )
                    sensor_box.add_widget(MDLabel(
                        text=f"[color=FFFFFF][b]Sensor ID: {sensor_info['id']}[/b][/color]",
                        markup=True,
                        size_hint_y=None,
                        height=dp(25),
                        halign='left'
                    ))
                    sensor_box.add_widget(MDLabel(
                        text=f"[color=FFFFFF]Time: {sensor_info['time']:.1f}s[/color]",
                        markup=True,
                        size_hint_y=None,
                        height=dp(25),
                        halign='left'
                    ))
                    sensor_box.add_widget(MDLabel(
                        text=f"[color=FFFFFF]CO²: {sensor_info['co2']:.0f} ppm[/color]",
                        markup=True,
                        size_hint_y=None,
                        height=dp(25),
                        halign='left'
                    ))
                    content_layout.add_widget(sensor_box)
                    total_height += dp(85) + dp(10)  # sensor_box height + spacing
                
                content_layout.height = total_height + dp(15)  # Add padding
                
                # Calculate popup size
                popup_height = min(dp(450), total_height + dp(80))  # +80 for title bar
                
                popup = Popup(
                    title="Data Points",
                    content=content_layout,
                    size_hint=(None, None),
                    size=(dp(280), popup_height)
                )
                popup.open()
            return True
        return super().on_touch_down(touch)


class DashboardScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller

        # --- Responsive scaling based on DPI ---
        base_dpi = 96.0
        self.scale = max(0.8, Window.dpi / base_dpi)

        app = MDApp.get_running_app()
        self.theme_cls = app.theme_cls

        # Track graph data and sensor ID mappings
        self.start_time = time.time()
        self.time_data_1, self.co2_data_1 = [], []
        self.time_data_2, self.co2_data_2 = [], []
        self.time_data_3, self.co2_data_3 = [], []
        self.time_data_4, self.co2_data_4 = [], []
        
        # Map sensor IDs to UI slots (will auto-populate as sensors send data)
        self.sensor_id_to_slot = {}  # {91: 1, 92: 2, 93: 3, 94: 4}
        self.slot_to_sensor_id = {}  # {1: 91, 2: 92, 3: 93, 4: 94}
        self.next_available_slot = 1

        # ---------------- Scrollable Root ----------------
        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        self.add_widget(scroll)

        # ---------------- Status Card ----------------
        status_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(60),
            padding=dp(8),
            radius=[12] * 4,
            md_bg_color=self.theme_cls.bg_light
        )
        self.status_label = MDLabel(
            text="Status: Idle",
            font_size=sp(16),
            halign="center",
            theme_text_color="Primary"
        )
        status_card.add_widget(self.status_label)
        content.add_widget(status_card)

        # ---------------- Graph Card ----------------
        graph_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(260),
            padding=dp(6),
            radius=[12] * 4,
            md_bg_color=self.theme_cls.bg_light
        )

        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=100 * self.scale)
        self.line1, = self.ax.plot([], [], color='red', marker='o', label='Sensor 1')
        self.line2, = self.ax.plot([], [], color='blue', marker='o', label='Sensor 2')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CO² (ppm)")
        self.ax.set_xlim(0, 60)
        self.ax.set_ylim(0, 2000)
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()

        self.graph_widget = GraphImage(size_hint=(1, 1))
        self.graph_widget.dashboard = self
        graph_card.add_widget(self.graph_widget)
        content.add_widget(graph_card)

        # ---------------- Live Readings ----------------
        live_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(300),  # Increased for 2x2 grid
            padding=dp(6),
            radius=[12] * 4,
            md_bg_color=self.theme_cls.bg_light,
        )
        live_card.add_widget(MDLabel(
            text="Live Readings",
            halign="center",
            font_style="H6"
        ))

        live_layout = GridLayout(
            cols=2,
            rows=2,
            spacing=dp(20),
            size_hint_y=None,
            height=dp(240),  # Increased height for 2x2 grid
            padding=[dp(20), 0]
        )

        def build_sensor_live(title):
            layout = MDBoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_x=None, width=dp(220))
            layout.add_widget(MDLabel(text=f"[b]{title}[/b]", markup=True,
                                      halign="center", font_size=sp(18)))
            
            # Sensor ID label (will be updated dynamically)
            val_sensor_id = MDLabel(
                text="[i]No sensor[/i]",
                markup=True,
                halign="center",
                font_size=sp(14),
                color=(0.6, 0.6, 0.6, 1)
            )
            layout.add_widget(val_sensor_id)
            
            grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(80))
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
            return layout, val_sensor_id, val_co2, val_temp, val_rh

        (sensor1_layout, self.lbl1_sensor_id, self.lbl1_co2,
         self.lbl1_temp, self.lbl1_rh) = build_sensor_live("Sensor Slot 1")
        (sensor2_layout, self.lbl2_sensor_id, self.lbl2_co2,
         self.lbl2_temp, self.lbl2_rh) = build_sensor_live("Sensor Slot 2")
        (sensor3_layout, self.lbl3_sensor_id, self.lbl3_co2,
         self.lbl3_temp, self.lbl3_rh) = build_sensor_live("Sensor Slot 3")
        (sensor4_layout, self.lbl4_sensor_id, self.lbl4_co2,
         self.lbl4_temp, self.lbl4_rh) = build_sensor_live("Sensor Slot 4")

        live_layout.add_widget(sensor1_layout)
        live_layout.add_widget(sensor2_layout)
        live_layout.add_widget(sensor3_layout)
        live_layout.add_widget(sensor4_layout)

        live_card.add_widget(live_layout)
        content.add_widget(live_card)

        # ---------------- Calibration Card ----------------
        calib_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(400),  # Increased for 2x2 grid
            padding=dp(12),
            radius=[12] * 4,
            md_bg_color=self.theme_cls.bg_light,
        )

        calib_card.add_widget(MDLabel(
            text="Calibration Averages (CO²)",
            halign="center",
            font_style="H6",
            size_hint_y=None,
            height=dp(32),
        ))

        calib_layout = GridLayout(
            cols=2,
            rows=2,
            spacing=dp(20),
            size_hint_y=None,
            height=dp(320),  # Increased for 2x2 grid
            padding=[dp(20), 0]
        )

        # helper to build calibration block
        def build_sensor_calib(title):
            layout = MDBoxLayout(
                orientation="vertical",
                spacing=dp(6),
                size_hint_x=None,
                width=dp(220),
            )
            layout.add_widget(MDLabel(
                text=f"[b]{title}[/b]",
                markup=True,
                halign="center",
                font_size=sp(16),
                size_hint_y=None,
                height=dp(30),
            ))

            grid = GridLayout(
                cols=2,
                spacing=dp(6),
                size_hint_y=None,
                height=dp(100)
            )

            lbl_baseline = MDLabel(text="Baseline:", halign="right")
            val_baseline = MDLabel(text="-- ppm", halign="left")
            lbl_exposure = MDLabel(text="Exposure:", halign="right")
            val_exposure = MDLabel(text="-- ppm", halign="left")
            lbl_post = MDLabel(text="Post-vent:", halign="right")
            val_post = MDLabel(text="-- ppm", halign="left")

            grid.add_widget(lbl_baseline); grid.add_widget(val_baseline)
            grid.add_widget(lbl_exposure); grid.add_widget(val_exposure)
            grid.add_widget(lbl_post); grid.add_widget(val_post)
            layout.add_widget(grid)

            return layout, val_baseline, val_exposure, val_post

        sensor1_calib, self.lbl1_baseline, self.lbl1_exposure, self.lbl1_vented = build_sensor_calib("Sensor Slot 1")
        sensor2_calib, self.lbl2_baseline, self.lbl2_exposure, self.lbl2_vented = build_sensor_calib("Sensor Slot 2")
        sensor3_calib, self.lbl3_baseline, self.lbl3_exposure, self.lbl3_vented = build_sensor_calib("Sensor Slot 3")
        sensor4_calib, self.lbl4_baseline, self.lbl4_exposure, self.lbl4_vented = build_sensor_calib("Sensor Slot 4")

        calib_layout.add_widget(sensor1_calib)
        calib_layout.add_widget(sensor2_calib)
        calib_layout.add_widget(sensor3_calib)
        calib_layout.add_widget(sensor4_calib)
        calib_card.add_widget(calib_layout)
        content.add_widget(calib_card)

        # ---------------- Buttons ----------------
        btn_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(70),
            spacing=dp(20)
        )
        btn_row.add_widget(MDRectangleFlatButton(text="Start", on_release=self.on_start))
        btn_row.add_widget(MDRectangleFlatButton(text="Stop", on_release=self.on_stop))
        
        self.gas_control_btn = MDRectangleFlatButton(text="Start Gas", on_release=self._gas_control)
        self.ventilation_control_btn = MDRectangleFlatButton(text="Start Circulation", on_release=self._ventilation_control)
        self.vent_control_btn = MDRectangleFlatButton(text="Start Vent", on_release=self._vent_control)
        self.stop_all_control_btn = MDRectangleFlatButton(text="Stop All", on_release=self._stop_all_control)

        btn_row.add_widget(self.gas_control_btn)
        btn_row.add_widget(self.ventilation_control_btn)
        btn_row.add_widget(self.vent_control_btn)
        btn_row.add_widget(self.stop_all_control_btn)
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

    def _gas_control(self, *_):
        if not self.controller.running:
            if self.gas_control_btn.text == "Start Gas":
                self.controller.esp32.start_gas()
                self.status_label.text = "Status: Gas ON"
                self.gas_control_btn.text = "Stop Gas"
            else:
                self.controller.esp32.stop_gas()
                self.status_label.text = "Status: Idle"
                self.gas_control_btn.text = "Start Gas"
    
    def _ventilation_control(self, *_):
        if not self.controller.running:
            if self.ventilation_control_btn.text == "Start Circulation":
                self.controller.esp32.start_circulation()
                self.status_label.text = "Status: Circulation ON"
                self.ventilation_control_btn.text = "Stop Circulation"
            else:
                self.controller.esp32.stop_circulation()
                self.status_label.text = "Status: Idle"
                self.ventilation_control_btn.text = "Start Circulation"
    
    def _vent_control(self, *_):  
        if not self.controller.running:
            if self.vent_control_btn.text == "Start Vent":
                self.controller.esp32.vent()
                self.status_label.text = "Status: Vent ON"
                self.vent_control_btn.text = "Stop Vent"
            else:
                self.controller.esp32.vent_off()
                self.status_label.text = "Status: Idle"
                self.vent_control_btn.text = "Start Vent"
    
    def _stop_all_control(self, *_):
        if not self.controller.running:
            self.controller.esp32.stop()
            self.status_label.text = "Status: Idle"
            self.gas_control_btn.text = "Start Gas"
            self.ventilation_control_btn.text = "Start Circulation"
            self.vent_control_btn.text = "Start Vent"

    # ---------------- Update Graph ----------------
    def _update_graph_image(self):
        self.ax.clear()
        
        # Plot all sensors dynamically based on slot assignments
        colors = ['red', 'blue', 'green', 'orange']
        data_map = {
            1: (self.time_data_1, self.co2_data_1),
            2: (self.time_data_2, self.co2_data_2),
            3: (self.time_data_3, self.co2_data_3),
            4: (self.time_data_4, self.co2_data_4),
        }
        
        all_times = []
        for slot in range(1, 5):
            if slot in self.slot_to_sensor_id:
                sensor_id = self.slot_to_sensor_id[slot]
                time_data, co2_data = data_map[slot]
                if time_data:  # Only plot if has data
                    self.ax.plot(
                        time_data, co2_data,
                        color=colors[slot-1],
                        marker='o',
                        label=f'Sensor ID {sensor_id}'
                    )
                    all_times.extend(time_data)
        
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CO₂ (ppm)")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        
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

                # Auto-assign sensor IDs to slots (1-4)
                if sensor_id not in self.sensor_id_to_slot:
                    if self.next_available_slot <= 4:
                        slot = self.next_available_slot
                        self.sensor_id_to_slot[sensor_id] = slot
                        self.slot_to_sensor_id[slot] = sensor_id
                        self.next_available_slot += 1
                        print(f"Assigned sensor_id {sensor_id} to slot {slot}")
                    else:
                        print(f"Warning: Max 4 sensors, ignoring sensor_id: {sensor_id}")
                        continue

                slot = self.sensor_id_to_slot[sensor_id]

                # Get label and data references for this slot
                labels_map = {
                    1: (self.lbl1_sensor_id, self.lbl1_co2, self.lbl1_temp,
                        self.lbl1_rh, self.time_data_1, self.co2_data_1),
                    2: (self.lbl2_sensor_id, self.lbl2_co2, self.lbl2_temp,
                        self.lbl2_rh, self.time_data_2, self.co2_data_2),
                    3: (self.lbl3_sensor_id, self.lbl3_co2, self.lbl3_temp,
                        self.lbl3_rh, self.time_data_3, self.co2_data_3),
                    4: (self.lbl4_sensor_id, self.lbl4_co2, self.lbl4_temp,
                        self.lbl4_rh, self.time_data_4, self.co2_data_4),
                }
                
                (lbl_sensor_id, lbl_co2, lbl_temp,
                 lbl_rh, time_data, co2_data) = labels_map[slot]

                # Update sensor ID label (once per sensor)
                if lbl_sensor_id.text == "[i]No sensor[/i]":
                    lbl_sensor_id.text = f"[b]Sensor ID: {sensor_id}[/b]"
                    lbl_sensor_id.color = (0.2, 0.6, 1.0, 1)  # Blue color

                # Update labels and data
                if co2 is not None:
                    lbl_co2.text = f"{co2:.0f} ppm"
                    time_data.append(elapsed)
                    co2_data.append(co2)

                    # Keep only last N minutes
                    while time_data and (elapsed - time_data[0] > MAX_TIME_WINDOW):
                        time_data.pop(0)
                        co2_data.pop(0)

                if temp is not None:
                    lbl_temp.text = f"{temp:.1f} °C"
                if rh is not None:
                    lbl_rh.text = f"{rh:.1f} %"

                self._update_graph_image()

            elif t == "struct_update":
                s = msg["struct"]

                for sid, val in s.items():
                    # Map sensor ID to slot
                    if sid not in self.sensor_id_to_slot:
                        # print(f"Warning: Sensor {sid} not mapped to a slot yet")
                        continue
                    
                    slot = self.sensor_id_to_slot[sid]
                    
                    baseline_val = "--" if val['baseline'] is None else f"{val['baseline']:.2f}"
                    exposure_val = "--" if val['exposure'] is None else f"{val['exposure']:.2f}"
                    vented_val = "--" if val['vented'] is None else f"{val['vented']:.2f}"

                    calib_labels_map = {
                        1: (self.lbl1_baseline, self.lbl1_exposure, self.lbl1_vented),
                        2: (self.lbl2_baseline, self.lbl2_exposure, self.lbl2_vented),
                        3: (self.lbl3_baseline, self.lbl3_exposure, self.lbl3_vented),
                        4: (self.lbl4_baseline, self.lbl4_exposure, self.lbl4_vented),
                    }
                    
                    lbl_baseline, lbl_exposure, lbl_vented = calib_labels_map[slot]
                    lbl_baseline.text = f"{baseline_val} ppm"
                    lbl_exposure.text = f"{exposure_val} ppm"
                    lbl_vented.text = f"{vented_val} ppm"
