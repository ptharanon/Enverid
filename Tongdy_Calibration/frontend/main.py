from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from backend.db import init_db, start_db_worker, db_queue
from backend.tongdy_sensor import TongdySensor
from backend.esp32_interface import ESP32Interface
from backend.poller import SensorPoller
from backend.calibration_controller import CalibrationController
from .screens.dashboard import DashboardScreen
from .screens.settings import SettingsScreen

class App(MDApp):
    def build(self):
        # DB + worker
        init_db()
        self.db_thread = start_db_worker()

        # Hardware
        self.sensor = TongdySensor(port="/dev/ttyUSB0", slave_address=1)  # adjust as needed
        # Give it a consistent id so DB rows have a sensor_id
        self.sensor.sensor_id = 1
        self.esp32 = ESP32Interface()  # GPIO23,24 active-low

        # Background services
        self.poller = SensorPoller(sensor=self.sensor, interval=60)
        self.poller.start()
        # Calibration controller uses CO2 samples every 5s during windows
        self.controller = CalibrationController(sensor=self.sensor, esp32=self.esp32, sample_period_s=5)

        # UI
        self.theme_cls.primary_palette = "Blue"
        sm = ScreenManager()
        sm.add_widget(DashboardScreen(controller=self.controller, name="dashboard"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def on_stop(self):
        # Graceful shutdown
        try:
            self.poller.stop()
        except Exception:
            pass
        db_queue.put({"type": "stop"})  # stop DB worker

