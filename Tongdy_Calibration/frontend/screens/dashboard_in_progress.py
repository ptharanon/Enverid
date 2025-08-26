from kivy.clock import Clock
from kivy.metrics import dp
from kivy_garden.graph import Graph, LinePlot

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.label import MDLabel

from backend.ui_queue import ui_queue
from collections import deque
import time
import queue


class DashboardScreen(MDBoxLayout):
    """
    Dashboard layout:
      [Status]
      [Realtime CO2 Graph]
      [Live Readings card]
      [Calibration Averages card]
      [Start | Stop buttons]
    """

    def __init__(self, controller, **kwargs):
        # super().__init__(orientation="vertical",
        #                  spacing=dp(8), padding=dp(12), **kwargs)
        super().__init__(**kwargs)
        self.ui_queue = ui_queue
        self.controller = controller

        # ---- plotting buffers & timing ----
        self.window_seconds = 300            # show last 5 minutes
        self.start_time = time.time()        # ✅ initialized
        self.times = deque(maxlen=1800)      # ✅ data arrays (time stamps)
        self.co2_values = deque(maxlen=1800) # ✅ data arrays (co2 ppm)

        # ---------- STATUS ----------
        self.status_label = MDLabel(
            text="Status: Ready",
            halign="center",
            font_style="H6",
            size_hint_y=None,
            height=dp(36),
        )
        self.add_widget(self.status_label)

        # ---------- REALTIME CO2 GRAPH (under Status) ----------
        graph_card = MDCard(orientation="vertical",
                            padding=(dp(10), dp(6), dp(10), dp(10)),
                            size_hint_y=0.50,  # occupies half of the screen height
                            radius=dp(12),
                            )
        graph_title = MDLabel(
            text="Real-time CO2",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(22),
        )
        graph_card.add_widget(graph_title)

        self.graph = Graph(
            xlabel="Time (s)",
            ylabel="CO2 (ppm)",
            x_ticks_minor=5,
            x_ticks_major=60,
            y_ticks_major=200,
            x_grid=True, y_grid=True,
            x_grid_label=True, y_grid_label=True,
            xmin=0, xmax=self.window_seconds,
            ymin=0, ymax=2000,
            padding=dp(5),
            size_hint=(1, 1),
        )
        self.plot = LinePlot(color=[0.0, 0.47, 1.0, 1])  # blue line
        self.graph.add_plot(self.plot)
        graph_card.add_widget(self.graph)
        self.add_widget(graph_card)

        # ---------- LIVE READINGS ----------
        live_card = MDCard(orientation="vertical",
                           padding=dp(12), size_hint_y=0.16, radius=dp(12))
        live_title = MDLabel(text="Live Readings", halign="center",
                             font_style="Subtitle1",
                             theme_text_color="Primary",
                             size_hint_y=None, height=dp(24))
        live_card.add_widget(live_title)

        row = MDBoxLayout(orientation="horizontal", spacing=dp(16))
        self.lbl_co2 = MDLabel(text="CO2: -- ppm", halign="center",
                               theme_text_color="Secondary")
        self.lbl_temp = MDLabel(text="Temp: -- °C", halign="center",
                                theme_text_color="Secondary")
        self.lbl_rh = MDLabel(text="RH: -- %", halign="center",
                              theme_text_color="Secondary")
        row.add_widget(self.lbl_co2)
        row.add_widget(self.lbl_temp)
        row.add_widget(self.lbl_rh)
        live_card.add_widget(row)
        self.add_widget(live_card)

        # ---------- CALIBRATION AVERAGES ----------
        avg_card = MDCard(orientation="vertical",
                          padding=dp(12), size_hint_y=0.16, radius=dp(12))
        avg_title = MDLabel(text="Calibration Averages (CO2)",
                            halign="center", font_style="Subtitle1",
                            theme_text_color="Primary",
                            size_hint_y=None, height=dp(24))
        avg_card.add_widget(avg_title)

        avg_row = MDBoxLayout(orientation="horizontal", spacing=dp(16))
        self.lbl_baseline = MDLabel(text="Baseline: --", halign="center",
                                    theme_text_color="Secondary")
        self.lbl_exposure = MDLabel(text="Exposure: --", halign="center",
                                    theme_text_color="Secondary")
        self.lbl_vented = MDLabel(text="Post-vent: --", halign="center",
                                  theme_text_color="Secondary")
        avg_row.add_widget(self.lbl_baseline)
        avg_row.add_widget(self.lbl_exposure)
        avg_row.add_widget(self.lbl_vented)
        avg_card.add_widget(avg_row)
        self.add_widget(avg_card)

        # ---------- CONTROLS ----------
        btn_row = MDBoxLayout(orientation="horizontal",
                              spacing=dp(10), size_hint_y=None, height=dp(48))
        self.btn_start = MDRectangleFlatButton(text="Start")
        self.btn_stop = MDRectangleFlatButton(text="Stop")

        self.btn_start.bind(on_release=lambda *_: self._on_start())
        self.btn_stop.bind(on_release=lambda *_: self._on_stop())
        btn_row.add_widget(self.btn_start)
        btn_row.add_widget(self.btn_stop)
        self.add_widget(btn_row)

        # consume UI queue regularly (5 fps feels smooth without being heavy)
        Clock.schedule_interval(self._consume_ui_queue, 1.0 / 5.0)

    # ---------- controls ----------
    def _on_start(self):
        if not self.controller.running:
            self.controller.start()
            self.status_label.text = "Status: Starting calibration..."

    def _on_stop(self):
        if self.controller.running:
            self.controller.stop()
            self.status_label.text = "Status: Stopped"

    # ---------- queue consumer ----------
    def _consume_ui_queue(self, _dt):
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                mtype = msg.get("type")

                if mtype == "status":
                    # accept 'value' or 'data' for backward compatibility
                    text = msg.get("value", msg.get("data", ""))
                    self.status_label.text = f"Status: {text}"

                elif mtype == "sensor":
                    data = msg.get("value", msg.get("data", {})) or {}
                    co2 = data.get("co2")
                    temp = data.get("temperature")
                    rh = data.get("humidity")

                    # update live labels
                    self.lbl_co2.text = f"CO2: {co2:.0f} ppm" if co2 is not None else "CO2: -- ppm"
                    self.lbl_temp.text = f"Temp: {temp:.1f} °C" if temp is not None else "Temp: -- °C"
                    self.lbl_rh.text = f"RH: {rh:.1f} %" if rh is not None else "RH: -- %"

                    # feed plot buffers
                    if co2 is not None:
                        t = time.time() - self.start_time
                        self.times.append(t)
                        self.co2_values.append(float(co2))
                        self._refresh_plot()

                elif mtype == "struct":
                    # expects dict with keys: baseline/exposure/vented each -> {"co2":..}
                    s = msg.get("value", msg.get("data", {})) or {}
                    self._update_struct_labels(s)

        except queue.Empty:
            pass

    # ---------- helpers ----------
    def _refresh_plot(self):
        """Update the points and keep a rolling window."""
        if not self.times:
            return

        # compute x-window
        t_now = self.times[-1]
        xmin = max(0.0, t_now - self.window_seconds)
        xmax = max(self.window_seconds, t_now)

        # select points within window
        pts = [(t, v) for (t, v) in zip(self.times, self.co2_values) if t >= xmin]
        self.plot.points = pts

        # update axes
        self.graph.xmin = xmin
        self.graph.xmax = xmax

        ys = [p[1] for p in pts] if pts else [0]
        y_min = max(0, min(ys) - 50)
        y_max = max(200, max(ys) + 50)
        self.graph.ymin = y_min
        self.graph.ymax = y_max

    def _update_struct_labels(self, s):
        def fmt(v):
            try:
                return f"{v.get('co2', None):.0f}" if v and v.get('co2') is not None else "--"
            except Exception:
                return "--"

        self.lbl_baseline.text = f"Baseline: {fmt(s.get('baseline'))}"
        self.lbl_exposure.text = f"Exposure: {fmt(s.get('exposure'))}"
        self.lbl_vented.text = f"Post-vent: {fmt(s.get('vented'))}"
