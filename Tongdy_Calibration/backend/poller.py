import threading, time
from .db import db_queue
from .ui_queue import ui_queue

class SensorPoller:
    """Reads sensor on interval; pushes to db_queue and ui_queue."""
    def __init__(self, sensor, interval=60):
        self.sensor = sensor
        self.interval = interval
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
        if self.thread:
            self.thread.join(timeout=2)

    def _run(self):
        while self.running:
            val = self.sensor.read_value()
            # UI update (live)
            ui_queue.put({"type": "sensor_value", "sensor_id": self.sensor.sensor_id, "value": val})
            # DB write batch (single reading here, but still via queue)
            db_queue.put({"type": "sensor_batch", "readings": [(self.sensor.sensor_id, val)]})
            time.sleep(self.interval)
