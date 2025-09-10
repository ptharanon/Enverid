import time, threading
from statistics import mean
from ..ui_queue import ui_queue
from ..db import db_queue

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

    def __init__(self, sensors, esp32, sample_period_s=5):
        self.TIME = 10 # debug timer 10s
        self.TIME_UNIT = "seconds"

        self.sensors = sensors
        self.esp32 = esp32
        self.sample_period_s = sample_period_s
        self.running = False
        self.thread = None
        self.struct = {s.sensor_id: {"baseline": None, "exposure": None, "vented": None} for s in sensors}

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._process, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        # ensure relays are off
        try:
            self.esp32.stop()
        except Exception:
            pass

    def _status(self, text: str):
        ui_queue.put({"type": "status", "text": text})

    def _push_struct(self, key: str, results: dict):
        # print(f"CalibrationController: {key} results: {results}")
        for sid, val in results.items():
            self.struct[sid][key] = val
        ui_queue.put({"type": "struct_update", "struct": dict(self.struct)})
    
    def _collect_avg(self, duration_s: int):
        values = {s.sensor_id: [] for s in self.sensors}
        start = time.time()
        while self.running and (time.time() - start < duration_s):
            for s in self.sensors:
                v = (s.read_values() or {}).get("co2")
                if v is not None:
                    values[s.sensor_id].append(float(v))
            time.sleep(self.sample_period_s)
        return {sid: (mean(vals) if vals else None) for sid, vals in values.items()}

    def _sleep_with_checks(self, duration_s: int):
        end = time.time() + duration_s
        while self.running and time.time() < end:
            time.sleep(0.25)

    def _process(self):
        try:
            # 1) Baseline
            self._status(f"Collecting baseline ({self.TIME} {self.TIME_UNIT})")
            avg = self._collect_avg(self.TIME)
            self._push_struct("baseline", avg)
            if not self.running: return

            # 2) Gas injection hold
            self._status(f"Injecting calibration gas ({self.TIME} {self.TIME_UNIT})")
            self.esp32.start_gas()
            self._sleep_with_checks(self.TIME)
            self.esp32.stop_gas()
            self.esp32.start_circulation()  # start circulation after gas injection
            if not self.running: return

            # 3) Exposure measurement
            self._status(f"Collecting exposure ({self.TIME} {self.TIME_UNIT})")
            avg = self._collect_avg(self.TIME)
            self._push_struct("exposure", avg)
            if not self.running: return

            # 4) Vent
            self._status(f"Venting ({self.TIME} {self.TIME_UNIT})")
            self.esp32.stop_circulation()  # stop circulation before venting
            self.esp32.vent()
            self._sleep_with_checks(self.TIME)
            self.esp32.vent_off()
            if not self.running: return

            # 5) Post-vent measurement
            self._status(f"Collecting post-vent ({self.TIME} {self.TIME_UNIT})")
            avg = self._collect_avg(self.TIME)
            self._push_struct("vented", avg)
            if not self.running: return

            # 6) Save
            self._status("Saving calibration record")
            for sid, res in self.struct.items():
                db_queue.put({
                    "type": "calibration",
                    "sensor_id": sid,
                    "baseline": res["baseline"],
                    "exposure": res["exposure"],
                    "vented": res["vented"],
                })
            self._status("Calibration complete")
        finally:
            self.running = False
            # Fail-safe: ensure all outputs are off
            try:
                self.esp32.stop()
                self.esp32.cleanup()
            except Exception:
                pass

        def manual_start_gas(self):
            self.esp32.start_gas()

        def manual_stop_gas(self):
            self.esp32.stop_gas()
        
        def manual_start_circulation(self):
            self.esp32.start_circulation()

        def manual_stop_circulation(self):
            self.esp32.stop_circulation()

        def manual_vent(self):
            self.esp32.vent()
        
        def manual_vent_off(self):
            self.esp32.vent_off()
        
        def manual_stop_all(self):
            self.esp32.stop()

# Exhaust + Motorize in/out added
