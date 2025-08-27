import random, time, math
from .base import BaseSensor

class MockSensor(BaseSensor):
    """
    Simulates CO2/Temp/RH. Phase-aware so calibration makes sense:
      baseline ~ 450±30 ppm, exposure ~ 1500±100 ppm, vented ~ 600±50 ppm.
    """
    def __init__(self, sensor_id):
        super().__init__(sensor_id)
        self.phase = "baseline"
        self.t0 = time.time()

    def set_phase(self, phase: str):
        self.phase = phase

    def read_values(self):
        t = time.time() - self.t0
        # gentle oscillation to look alive
        wiggle = 0.5 * math.sin(t / 15.0)

        if self.phase == "baseline":
            co2 = 450 + 30 * random.random() + 15 * wiggle
        elif self.phase == "exposure":
            co2 = 1500 + 100 * random.random() + 60 * wiggle
        else:  # 'vented'
            co2 = 600 + 50 * random.random() + 30 * wiggle

        temperature = 25.0 + 0.2 * math.sin(t / 60.0) + random.uniform(-0.1, 0.1)
        humidity = 55.0 + 1.0 * math.sin(t / 40.0) + random.uniform(-0.5, 0.5)

        return {"co2": round(co2, 1), "temperature": round(temperature, 2), "humidity": round(humidity, 2)}
