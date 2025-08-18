from .base_sensor import BaseSensor
import random

class TongdySensor(BaseSensor):
    def read_data(self):
        # mock sensor data
        return random.uniform(400, 2000)  

    def calibrate(self):
        print("Calibrating CO2 sensor...")