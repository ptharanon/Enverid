# backend/tongdy_sensor.py
import random

class TongdySensor:
    def __init__(self, sensor_id: int, name: str = "Tongdy CO2 Sensor"):
        self.sensor_id = sensor_id
        self.name = name

    def read_value(self) -> float:
        """Simulate reading a CO2 value (ppm)."""
        return 400 + random.uniform(-5, 5)  # around fresh-air baseline
