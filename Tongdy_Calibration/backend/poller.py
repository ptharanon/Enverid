import threading, time
import random

from .db import db_queue
from .ui_queue import ui_queue

class SensorPoller:
    """Reads sensor on interval; pushes to db_queue and ui_queue."""
    def __init__(self, sensors, interval=60, jitter=(0.02, 0.08)):
        # print("SensorPoller init with sensors:", sensors)
        self.sensors = sensors
        self.interval = interval
        self.jitter = jitter
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

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
        next_poll = time.time()
        while self.running:
            for s in self.sensors:
                # print("Polling sensor", getattr(s, "sensor_id", 1))
                try:
                    vals = s.read_values() or {}
                except Exception as e:
                    # logger.exception(f"Unhandled error reading sensor {getattr(s, 'sensor_id', '?')}: {e}")
                    vals = {"co2": None, "temperature": None, "humidity": None}
                co2 = vals.get("co2")
                temp = vals.get("temperature")
                rh   = vals.get("humidity")

                # UI: show live values (even if some are None)
                ui_queue.put({
                    "type": "live_values", 
                    "data": {
                        "co2": co2, 
                        "temperature": temp, # Type_K only has temp 
                        "humidity": rh,
                        "sensor_id": s.sensor_id if hasattr(s, "sensor_id") else 1,
                        "sensor_type": s.sensor_type if hasattr(s, "sensor_type") else "unknown" # 'Tongdy', 'Type_K'
                }})

                batch = []
                if co2 is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "co2", co2))
                if temp is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "temperature", float(temp)))
                if rh   is not None: 
                    batch.append((s.sensor_id if hasattr(s, "sensor_id") else 1, "humidity", float(rh)))
                if batch:
                    db_queue.put({"type": "sensor_batch", "readings": batch})
                
                if self.jitter:
                    time.sleep(random.uniform(self.jitter[0], self.jitter[1]))

            next_poll += self.interval
            sleep_time = max(0.0, next_poll - time.time())
            if sleep_time > 0:
                # use event.wait for responsive stop
                self._stop_event.wait(sleep_time)
            else:
                # behind schedule: reset baseline
                next_poll = time.time()

