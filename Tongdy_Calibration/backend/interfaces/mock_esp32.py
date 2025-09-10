class MockESP32Interface:
    """
    Prints actions instead of toggling GPIO. Optionally nudges a MockSensor's phase
    if you pass it in (not required).
    """
    def __init__(self, sensors=None):
        self.sensors = sensors or []

    def _set_phase_all(self, phase: str):
        for sensor in self.sensors:
            if hasattr(sensor, "set_phase"):
                sensor.set_phase(phase)

    def start_gas(self):
        print("[MOCK] Gas ON")
        self._set_phase_all("exposure")

    def stop_gas(self): print("[MOCK] Gas OFF")

    def start_circulation(self): 
        print("[MOCK] Circulation ON")

    def stop_circulation(self): print("[MOCK] Circulation OFF")

    def vent(self):
        print("[MOCK] Vent ON")
        self._set_phase_all("vented")

    def vent_off(self): print("[MOCK] Vent OFF")

    def stop(self): print("[MOCK] Stop all relays")

    def cleanup(self): print("[MOCK] Cleanup GPIO")