from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from frontend.screens.dashboard import DashboardScreen
from sensors.tongdy_sensor import CO2Sensor
from backend.poller import SensorPoller
from backend.data_logger import db_queue

class SensorApp(MDApp):
    def build(self):
        self.poller = SensorPoller(interval=60)
        # Add multiple sensors
        self.poller.add_sensor(sensor_id=1, sensor_obj=CO2Sensor())
        self.poller.add_sensor(sensor_id=2, sensor_obj=CO2Sensor())
        self.poller.add_sensor(sensor_id=3, sensor_obj=CO2Sensor())
        self.poller.start()

        sm = ScreenManager()
        sm.add_widget(DashboardScreen(name="dashboard"))
        return sm

    def on_stop(self):
        self.poller.stop()
        db_queue.put(None)  # stop DB worker

if __name__ == "__main__":
    SensorApp().run()
