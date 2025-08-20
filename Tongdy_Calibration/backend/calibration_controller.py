import time, threading
from statistics import mean
from .ui_queue import ui_queue
from .db import db_queue

class CalibrationController:
    """
    Business flow:
    1) Baseline 5m -> avg
    2) ESP32 start gas 5m -> stop
    3) Exposure 5m -> avg
    4) ESP32 vent 5m -> stop
    5) Vented 5m -> avg
    6) Save calibration record
    """

    def __init__(self, sensor, esp32, sample_period_s=5):
        self.TIME = 10 # debug timer 10s
        self.sensor = sensor
        self.esp32 = esp32
        self.sample_period_s = sample_period_s
        self.running = False
        self.thread = None
        self.struct = {"baseline": None, "exposure": None, "vented": None}

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._process, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _status(self, text: str):
        ui_queue.put({"type": "status", "text": text})

    def _push_struct(self, key: str, value):
        self.struct[key] = value
        ui_queue.put({"type": "struct_update", "struct": dict(self.struct)})

    def _collect_avg(self, duration_s: int):
        values = []
        start = time.time()
        while self.running and (time.time() - start < duration_s):
            v = self.sensor.read_value()
            values.append(v)
            # optional: show sample during collection
            ui_queue.put({"type": "sensor_value", "sensor_id": self.sensor.sensor_id, "value": v})
            time.sleep(self.sample_period_s)
        return (mean(values) if values else None)

    def _sleep_with_checks(self, duration_s: int):
        end = time.time() + duration_s
        while self.running and time.time() < end:
            time.sleep(0.25)

    def _process(self):
        try:
            # 1) Baseline
            self._status("Collecting baseline (5 min)")
            avg = self._collect_avg(self.TIME)
            self._push_struct("baseline", avg)
            if not self.running: return

            # 2) Gas injection hold
            self._status("Injecting calibration gas (5 min)")
            self.esp32.start_gas()
            self._sleep_with_checks(self.TIME)
            self.esp32.stop()
            if not self.running: return

            # 3) Exposure measurement
            self._status("Collecting exposure (5 min)")
            avg = self._collect_avg(self.TIME)
            self._push_struct("exposure", avg)
            if not self.running: return

            # 4) Vent
            self._status("Venting (5 min)")
            self.esp32.vent()
            self._sleep_with_checks(self.TIME)
            self.esp32.stop()
            if not self.running: return

            # 5) Post-vent measurement
            self._status("Collecting post-vent (5 min)")
            avg = self._collect_avg(self.TIME)
            self._push_struct("vented", avg)
            if not self.running: return

            # 6) Save to DB (via db_queue)
            self._status("Saving calibration record")
            db_queue.put({
                "type": "calibration",
                "sensor_id": self.sensor.sensor_id,
                "baseline": self.struct["baseline"],
                "exposure": self.struct["exposure"],
                "vented": self.struct["vented"],
            })
            self._status("Calibration complete")
        finally:
            self.running = False
