import random

class TongdySensor:
    def __init__(self, sensor_id: int, name="Tongdy CO2"):
        self.sensor_id = sensor_id
        self.name = name
        self.calibration_offset = 0.0

    def read_value(self) -> float:
        # Replace with actual sensor read code
        raw = 400 + random.uniform(-20, 20)
        return raw + self.calibration_offset