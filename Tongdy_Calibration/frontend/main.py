from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from backend.db import init_db, start_db_worker, db_queue

from backend.sensors.tongdy_sensor import TongdySensor
from backend.sensors.mock_sensor import MockSensor # for testing
from backend.interfaces.esp32_interface import ESP32Interface
from backend.interfaces.mock_esp32 import MockESP32Interface # for testing

from backend.poller import SensorPoller
from backend.controller.calibration_controller import CalibrationController
from .screens.dashboard import DashboardScreen
from .screens.settings import SettingsScreen

class App(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_mock = True # for testing without hardware

    def build(self):
        # DB + worker
        init_db()
        self.db_thread = start_db_worker()

        # Hardware
        if self.use_mock:
            self.sensors = [MockSensor(sensor_id=1), MockSensor(sensor_id=2)]  # two mock sensors
            self.esp32 = MockESP32Interface(sensors=self.sensors)
        else:
            self.sensor = TongdySensor(port="/dev/ttyUSB0", slave_address=1)  # adjust as needed
            # Give it a consistent id so DB rows have a sensor_id
            self.sensor.sensor_id = 1
            self.esp32 = ESP32Interface()  # GPIO23,24 active-low


        # Background services
        self.poller = SensorPoller(sensors=self.sensors, interval=10)
        self.poller.start()
        # Calibration controller uses CO2 samples every 5s during windows
        self.controller = CalibrationController(sensors=self.sensors, esp32=self.esp32, sample_period_s=5)

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

