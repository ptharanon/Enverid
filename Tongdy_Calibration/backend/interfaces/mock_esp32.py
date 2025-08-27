class MockESP32Interface:
    """
    Prints actions instead of toggling GPIO. Optionally nudges a MockSensor's phase
    if you pass it in (not required).
    """
    def __init__(self, sensor=None):
        self.sensor = sensor

    def start_gas(self):
        print("[MOCK] Gas ON")
        if hasattr(self.sensor, "set_phase"): self.sensor.set_phase("exposure")

    def stop_gas(self): print("[MOCK] Gas OFF")

    def vent(self):
        print("[MOCK] Vent ON")
        if hasattr(self.sensor, "set_phase"): self.sensor.set_phase("vented")

    def vent_off(self): print("[MOCK] Vent OFF")

    def stop(self): print("[MOCK] Stop all relays")

    def cleanup(self): print("[MOCK] Cleanup GPIO")