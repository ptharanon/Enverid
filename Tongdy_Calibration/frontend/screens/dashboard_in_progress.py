"""
Refactored Kivy/KivyMD dashboard split into two screens:
 - DashboardScreen: status, live readings, calibration, start/stop, navigation button to graph
 - GraphScreen: full-screen interactive Matplotlib graph (touch to show nearest points)

Shared DataModel holds time-series data. DashboardScreen drains ui_queue and updates DataModel.
GraphScreen reads DataModel and renders Matplotlib figure into a Kivy texture.

This single-file example also contains a MockController in __main__ for local testing.
Adapt the Controller integration to your existing controller by passing `controller` into
DashboardScreen and GraphScreen (both accept controller, but only DashboardScreen uses it).

Notes:
 - Keep matplotlib backend 'Agg' for PNG rendering to texture.
 - Use a threading.Lock in DataModel because Controller may push data from background threads.
 - GraphScreen uses a "request_refresh()" mechanism to avoid excessive redraws.
 - Window.dpi may be unreliable on some Raspberry Pi builds; the code computes a scale
   but also recomputes the figure size using the graph widget size when rendering.

"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp, sp
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import ObjectProperty, NumericProperty
from kivy.core.window import Window
from kivy.lang import Builder

from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.toolbar import MDTopAppBar

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import time
import threading
from queue import Queue

# Replace with your existing ui_queue import
try:
    from backend.ui_queue import ui_queue
except Exception:
    # For standalone testing, create a local queue
    ui_queue = Queue()

MAX_TIME_WINDOW = 300  # seconds
BASE_DPI = 96.0


class DataModel:
    """Shared container for time-series data. Thread-safe for append/read operations."""
    def __init__(self):
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.time_data_1 = []
        self.co2_data_1 = []
        self.time_data_2 = []
        self.co2_data_2 = []

    def append(self, sensor_id, elapsed, co2):
        with self.lock:
            if sensor_id == 1:
                self.time_data_1.append(elapsed)
                self.co2_data_1.append(co2)
                # trim
                while self.time_data_1 and (elapsed - self.time_data_1[0] > MAX_TIME_WINDOW):
                    self.time_data_1.pop(0)
                    self.co2_data_1.pop(0)
            else:
                self.time_data_2.append(elapsed)
                self.co2_data_2.append(co2)
                while self.time_data_2 and (elapsed - self.time_data_2[0] > MAX_TIME_WINDOW):
                    self.time_data_2.pop(0)
                    self.co2_data_2.pop(0)

    def snapshot(self):
        """Return a shallow copy of current lists for safe reading in UI thread."""
        with self.lock:
            return (
                list(self.time_data_1),
                list(self.co2_data_1),
                list(self.time_data_2),
                list(self.co2_data_2),
                self.start_time,
            )


class GraphImage(Image):
    """Image widget that detects touches and queries the DataModel for nearest points."""
    model = ObjectProperty(None)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.model is not None:
            # compute local x in 0..1
            local_x = (touch.x - self.x) / max(1.0, self.width)

            t1, c1, t2, c2, start_time = self.model.snapshot()
            all_times = t1 + t2
            if not all_times:
                return super().on_touch_down(touch)

            min_time, max_time = min(all_times), max(all_times)
            touch_time = min_time + local_x * (max_time - min_time)

            # find nearest points
            def nearest(lst_t, lst_c):
                if not lst_t:
                    return (None, None)
                idx = min(range(len(lst_t)), key=lambda i: abs(lst_t[i] - touch_time))
                return (lst_t[idx], lst_c[idx])

            nearest_1 = nearest(t1, c1)
            nearest_2 = nearest(t2, c2)

            msg = ""
            if nearest_1[0] is not None:
                msg += f"Sensor 1\nTime: {nearest_1[0]:.1f}s\nCO²: {nearest_1[1]:.0f} ppm\n\n"
            if nearest_2[0] is not None:
                msg += f"Sensor 2\nTime: {nearest_2[0]:.1f}s\nCO²: {nearest_2[1]:.0f} ppm"

            if msg:
                popup = Popup(title="Data Point",
                              content=Label(text=msg),
                              size_hint=(None, None),
                              size=(dp(220), dp(220)))
                popup.open()

            return True
        return super().on_touch_down(touch)


class DashboardScreen(Screen):
    def __init__(self, controller, model: DataModel, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.model = model

        # --- Responsive scaling based on DPI ---
        self.scale = max(0.8, Window.dpi / BASE_DPI) if Window.dpi else 1.0

        app = MDApp.get_running_app()
        if app:
            self.theme_cls = app.theme_cls

        # Track graph-related start time via model
        self.model.start_time = self.model.start_time

        # ---------------- Root layout (scrollable) ----------------
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
        )
        self.status_label = MDLabel(
            text="Status: Idle",
            font_size=sp(16),
            halign="center",
            theme_text_color="Primary"
        )
        status_card.add_widget(self.status_label)
        content.add_widget(status_card)

        # ---------------- Live Readings ----------------
        live_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(180),
            padding=dp(6),
            radius=[12] * 4,
        )
        live_card.add_widget(MDLabel(
            text="Live Readings",
            halign="center",
            font_style="H6"
        ))

        live_layout = GridLayout(
            cols=2,
            spacing=dp(40),
            size_hint_y=None,
            height=dp(120),
            padding=[dp(40), 0]
        )

        def build_sensor_live(title):
            layout = MDBoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_x=None, width=dp(220))
            layout.add_widget(MDLabel(text=f"[b]{title}[/b]", markup=True,
                                      halign="center", font_size=sp(18)))
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
            return layout, val_co2, val_temp, val_rh

        sensor1_layout, self.lbl1_co2, self.lbl1_temp, self.lbl1_rh = build_sensor_live("Sensor 1")
        sensor2_layout, self.lbl2_co2, self.lbl2_temp, self.lbl2_rh = build_sensor_live("Sensor 2")
        live_layout.add_widget(sensor1_layout)
        live_layout.add_widget(sensor2_layout)

        live_card.add_widget(live_layout)
        content.add_widget(live_card)

        # ---------------- Calibration Card ----------------
        calib_card = MDCard(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(220),
            padding=dp(12),
            radius=[12] * 4,
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
            spacing=dp(40),
            size_hint_y=None,
            height=dp(160),
            padding=[dp(40), 0]
        )

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

        sensor1_calib, self.lbl1_baseline, self.lbl1_exposure, self.lbl1_vented = build_sensor_calib("Sensor 1 Calibration")
        sensor2_calib, self.lbl2_baseline, self.lbl2_exposure, self.lbl2_vented = build_sensor_calib("Sensor 2 Calibration")

        calib_layout.add_widget(sensor1_calib)
        calib_layout.add_widget(sensor2_calib)
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
        btn_row.add_widget(MDRectangleFlatButton(text="View Graph", on_release=self._show_graph))
        content.add_widget(btn_row)

        # Schedule UI refresh
        Clock.schedule_interval(self._drain_ui_queue, 1)

    # ---------------- Controller ----------------
    def on_start(self, *_):
        if self.controller and not getattr(self.controller, 'running', False):
            try:
                self.controller.start()
            except Exception:
                # controller may not implement start
                pass

    def on_stop(self, *_):
        if self.controller and getattr(self.controller, 'running', False):
            try:
                self.controller.stop()
                self.status_label.text = "Status: Stopping..."
            except Exception:
                pass

    def _show_graph(self, *_):
        if self.manager:
            self.manager.current = 'graph'

    # ---------------- UI Queue Handler ----------------
    def _drain_ui_queue(self, dt):
        refreshed = False
        while not ui_queue.empty():
            msg = ui_queue.get()
            t = msg.get("type")

            if t == "status":
                self.status_label.text = f"Status: {msg.get('text', '')}"

            elif t == "live_values":
                data = msg.get("data", {})
                sensor_id = data.get("sensor_id", 1)
                co2 = data.get("co2")
                temp = data.get("temperature")
                rh = data.get("humidity")
                elapsed = time.time() - self.model.start_time

                if sensor_id == 1:
                    if co2 is not None:
                        self.lbl1_co2.text = f"{co2:.0f} ppm"
                        self.model.append(1, elapsed, co2)
                        refreshed = True
                    if temp is not None: self.lbl1_temp.text = f"{temp:.1f} °C"
                    if rh is not None: self.lbl1_rh.text = f"{rh:.1f} %"
                else:
                    if co2 is not None:
                        self.lbl2_co2.text = f"{co2:.0f} ppm"
                        self.model.append(sensor_id, elapsed, co2)
                        refreshed = True
                    if temp is not None: self.lbl2_temp.text = f"{temp:.1f} °C"
                    if rh is not None: self.lbl2_rh.text = f"{rh:.1f} %"

            elif t == "struct_update":
                s = msg.get("struct", {})
                for sid, val in s.items():
                    baseline_val = "--" if val.get('baseline') is None else f"{val['baseline']:.2f}"
                    exposure_val = "--" if val.get('exposure') is None else f"{val['exposure']:.2f}"
                    vented_val = "--" if val.get('vented') is None else f"{val['vented']:.2f}"

                    if sid == 1:
                        self.lbl1_baseline.text = f"{baseline_val} ppm"
                        self.lbl1_exposure.text = f"{exposure_val} ppm"
                        self.lbl1_vented.text = f"{vented_val} ppm"
                    else:
                        self.lbl2_baseline.text = f"{baseline_val} ppm"
                        self.lbl2_exposure.text = f"{exposure_val} ppm"
                        self.lbl2_vented.text = f"{vented_val} ppm"

        # if new data arrived, ask graph screen to refresh (coalesce refreshes)
        if refreshed and self.manager:
            try:
                graph_screen = self.manager.get_screen('graph')
                graph_screen.request_refresh()
            except Exception:
                pass


class GraphScreen(Screen):
    """Full-screen graph. Reads DataModel snapshot and draws into texture."""
    def __init__(self, controller, model: DataModel, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.model = model
        self._needs_refresh = False

        # DPI/scale
        self.scale = max(0.8, Window.dpi / BASE_DPI) if Window.dpi else 1.0

        # Top bar with back button
        layout = MDBoxLayout(orientation='vertical')
        top = MDTopAppBar(title='Graph', left_action_items=[['arrow-left', lambda x: self._back_to_dashboard()]])
        layout.add_widget(top)

        # Card to contain the image (makes padding consistent)
        graph_card = MDCard(orientation='vertical', size_hint=(1, 1), padding=dp(6), radius=[12] * 4)

        # Matplotlib figure + axes (lines pre-created to allow set_data)
        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=100 * self.scale)
        self.line1, = self.ax.plot([], [], marker='o', label='Sensor 1')
        self.line2, = self.ax.plot([], [], marker='o', label='Sensor 2')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CO₂ (ppm)")
        self.ax.set_ylim(0, 2000)
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()

        self.graph_widget = GraphImage(size_hint=(1, 1))
        self.graph_widget.model = self.model
        graph_card.add_widget(self.graph_widget)
        layout.add_widget(graph_card)
        self.add_widget(layout)

        # schedule a low-rate auto-refresh in case there are continuous updates
        Clock.schedule_interval(self._auto_refresh, 0.8)

        # also listen to size changes to make the figure match widget pixel size
        self.graph_widget.bind(size=lambda *_: self.request_refresh())

    def _back_to_dashboard(self):
        if self.manager:
            self.manager.current = 'dashboard'

    def request_refresh(self):
        """Mark that we need to refresh and schedule a short Clock callback.
        Coalesces multiple requests into a single redraw in the next frame.
        """
        if not self._needs_refresh:
            self._needs_refresh = True
            Clock.schedule_once(self._do_refresh, 0)

    def _auto_refresh(self, dt):
        # If controller continuously pushes data, this ensures the graph moves.
        if self._needs_refresh:
            self._do_refresh(0)

    def _do_refresh(self, dt):
        self._needs_refresh = False
        # take a snapshot of data
        t1, c1, t2, c2, start_time = self.model.snapshot()

        # avoid drawing if no size yet
        w, h = int(self.graph_widget.width), int(self.graph_widget.height)
        if w <= 2 or h <= 2:
            return

        try:
            # update line data and axes limits
            self.line1.set_data(t1, c1)
            self.line2.set_data(t2, c2)

            all_times = t1 + t2
            if all_times:
                min_time = min(all_times)
                max_time = max(all_times)
                if max_time - min_time < MAX_TIME_WINDOW:
                    max_time = min_time + MAX_TIME_WINDOW
                self.ax.set_xlim(min_time, max_time)
            else:
                self.ax.set_xlim(0, MAX_TIME_WINDOW)

            # recompute figure pixel size -> inches for matplotlib
            dpi = max(60, 100 * self.scale)
            self.fig.set_dpi(dpi)
            fig_w = max(2, w / float(dpi))
            fig_h = max(1, h / float(dpi))
            self.fig.set_size_inches(fig_w, fig_h)

            # redraw into PNG buffer
            buf = io.BytesIO()
            self.fig.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            self.graph_widget.texture = CoreImage(buf, ext='png').texture
            buf.close()
        except Exception as exc:
            # protect UI from plotting errors
            print('Graph render error:', exc)


class RootScreenManager(ScreenManager):
    pass


class DashboardApp(MDApp):
    def __init__(self, controller=None, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.model = DataModel()

    def build(self):
        sm = RootScreenManager(transition=SlideTransition())
        dash = DashboardScreen(controller=self.controller, model=self.model, name='dashboard')
        graph = GraphScreen(controller=self.controller, model=self.model, name='graph')
        sm.add_widget(dash)
        sm.add_widget(graph)
        return sm


# ----------------- Demo / Test harness -----------------
if __name__ == '__main__':
    # Simple mock controller that pushes data into ui_queue for demo purposes
    class MockController:
        def __init__(self):
            self.running = False
            self.thread = None

        def start(self):
            if self.running:
                return
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

        def stop(self):
            self.running = False

        def _run(self):
            import random
            t0 = time.time()
            sid = 1
            while self.running:
                # alternate sensors
                sid = 1 if sid == 2 else 2
                now = time.time()
                co2 = 400 + 1000 * random.random()
                temp = 20 + 5 * random.random()
                rh = 30 + 60 * random.random()
                ui_queue.put({
                    'type': 'live_values',
                    'data': {
                        'sensor_id': sid,
                        'co2': co2,
                        'temperature': temp,
                        'humidity': rh,
                    }
                })
                time.sleep(1.0)

    controller = MockController()
    app = DashboardApp(controller=controller)
    app.run()
