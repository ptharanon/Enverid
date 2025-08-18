import threading, time
from backend.data_logger import db_queue
from backend.calibration import CalibrationManager
from backend.ui_queue import ui_queue

class SensorPoller:
    def __init__(self, interval=60):
        self.interval = interval
        self.running = False
        self.thread = None
        self.calibration = CalibrationManager()
        self.sensors = {}  # {sensor_id: sensor_obj}

    def add_sensor(self, sensor_id, sensor_obj):
        self.sensors[sensor_id] = sensor_obj

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _run(self):
        while self.running:
            batch_readings = []
            for sensor_id, sensor in self.sensors.items():
                raw = sensor.read_data()
                calibrated = self.calibration.apply_calibration(sensor_id, raw)

                batch_readings.append((sensor_id, calibrated))
                ui_queue.put((sensor_id, calibrated))  # push to UI

            db_queue.put(batch_readings)  # push to DB
            time.sleep(self.interval)
