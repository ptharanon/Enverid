import threading, time
from .db import db_queue
from .ui_queue import ui_queue

class SensorPoller:
    """Reads sensor on interval; pushes to db_queue and ui_queue."""
    def __init__(self, sensors, interval=60):
        # print("SensorPoller init with sensors:", sensors)
        self.sensors = sensors
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
            for s in self.sensors:
                # print("Polling sensor", getattr(s, "sensor_id", 1))
                vals = s.read_values() or {}
                co2 = vals.get("co2")
                temp = vals.get("temperature")
                rh   = vals.get("humidity")

                # UI: show live values (even if some are None)
                ui_queue.put({
                    "type": "live_values", 
                    "data": {
                        "co2": co2, 
                        "temperature": temp, 
                        "humidity": rh,
                        "sensor_id": s.sensor_id if hasattr(s, "sensor_id") else 1
                }})

                # DB: store what we have
                batch = []
                if co2 is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "co2", co2))
                if temp is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "temperature", float(temp)))
                if rh   is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "humidity", float(rh)))
                if batch:
                    db_queue.put({"type": "sensor_batch", "readings": batch})

            time.sleep(self.interval)
