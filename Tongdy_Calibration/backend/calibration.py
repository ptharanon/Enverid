class CalibrationManager:
    def __init__(self):
        self.calibration_offsets = {}

    def set_calibration(self, sensor_id: int, offset: float):
        self.calibration_offsets[sensor_id] = offset

    def apply_calibration(self, sensor_id: int, raw_value: float) -> float:
        offset = self.calibration_offsets.get(sensor_id, 0.0)
        return raw_value + offset
