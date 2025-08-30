import logging
import time

logger = logging.getLogger(__name__)

MODE = {
    "GPIO": "GPIO",
    "REST": "REST",
    "MOCK": "MOCK"
}

CURRENT_MODE = MODE["MOCK"]   # Change as needed: GPIO, REST, MOCK (DEFAULT)

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except ImportError:
    GPIO = None
    _HAS_GPIO = False
    logger.warning("Warning: RPi.GPIO not available; GPIO functions will be no-ops.")

try:
    import requests
    _HAS_REST = True
except ImportError:
    requests = None
    _HAS_REST = False
    logger.warning("Warning: requests not available; REST-API functions will be no-ops.")


# ---------------- Base Interface ---------------- #

class BaseESP32Interface:
    """ Abstract interface definition for controlling gas valve and vent. """
    def start_gas(self): raise NotImplementedError
    def stop_gas(self): raise NotImplementedError
    def vent(self): raise NotImplementedError
    def vent_off(self): raise NotImplementedError
    def stop(self): raise NotImplementedError
    def cleanup(self): raise NotImplementedError

    def _set_phase_all(self, phase: str):
        for sensor in self.sensors:
            if hasattr(sensor, "set_phase"):
                sensor.set_phase(phase)

    def _retry_command(self, func, max_retries=3, delay=1.0):
        """Generic retry wrapper. Returns True if success, False if failed."""
        for attempt in range(1, max_retries + 1):
            if func():
                return True
            logger.warning(f"Attempt {attempt} failed, retrying...")
            time.sleep(delay)
        logger.error(f"Command failed after {max_retries} attempts")
        return False

# ---------------- GPIO Implementation ---------------- #

class GPIOESP32Interface(BaseESP32Interface):
    """ Raspberry Pi GPIO relay control (2 channels) with active-LOW logic. """

    def __init__(self, gas_pin=23, vent_pin=24, sensors=None):
        if not _HAS_GPIO:
            raise RuntimeError("RPi.GPIO not available on this platform.")

        self.sensors = sensors if sensors is not None else []
        self.gas_pin = gas_pin
        self.vent_pin = vent_pin

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Active-LOW relays; HIGH = OFF (safe default)
        GPIO.setup(self.gas_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.vent_pin, GPIO.OUT, initial=GPIO.HIGH)

        logger.info(f"Relay interface ready (gas={self.gas_pin}, vent={self.vent_pin})")

    def start_gas(self):
        GPIO.output(self.gas_pin, GPIO.LOW)
        logger.info("Gas valve ON")

    def stop_gas(self):
        GPIO.output(self.gas_pin, GPIO.HIGH)
        logger.info("Gas valve OFF")

    def vent(self):
        GPIO.output(self.vent_pin, GPIO.LOW)
        logger.info("Vent fan ON")

    def vent_off(self):
        GPIO.output(self.vent_pin, GPIO.HIGH)
        logger.info("Vent fan OFF")

    def stop(self):
        GPIO.output(self.gas_pin, GPIO.HIGH)
        GPIO.output(self.vent_pin, GPIO.HIGH)
        logger.info("All relays OFF")

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleaned up")


# ---------------- REST API Implementation ---------------- #

class RestESP32Interface(BaseESP32Interface):
    """ REST API based relay control. """
    def __init__(self, sensors=None, target_ip_address="http://192.168.1.99"):
        if not _HAS_REST:
            raise RuntimeError("requests not available on this platform.")

        self.sensors = sensors if sensors is not None else []
        self.base_url = target_ip_address.rstrip("/")
        logger.info(f"REST interface ready (base URL={self.base_url})")

    def _send_command(self, command: str):
        url = f"{self.base_url}/command/{command}"
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                logger.info(f"Command '{command}' sent successfully")
                return True
            else:
                logger.error(f"Command '{command}' failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return False

    def start_gas(self): 
        self._retry_command(lambda: self._send_command("start_gas"))
        self._set_phase_all("exposure")

    def stop_gas(self): 
        self._retry_command(lambda: self._send_command("stop_gas"))
        self._set_phase_all("exposure")

    def vent(self): 
        self._retry_command(lambda: self._send_command("start_vent"))
        self._set_phase_all("vented")

    def vent_off(self): 
        self._retry_command(lambda: self._send_command("stop_vent"))
        self._set_phase_all("baseline")

    def stop(self): 
        self._retry_command(lambda: self._send_command("stop"))
        self._set_phase_all("baseline")

    def cleanup(self): 
        self._retry_command(lambda: self._send_command("cleanup"))
        self._set_phase_all("baseline")


# ---------------- MOCK Implementation ---------------- #

class MockESP32Interface(BaseESP32Interface):
    """ Mock interface for testing. """

    def start_gas(self): print("MOCK: start_gas()")
    def stop_gas(self): print("MOCK: stop_gas()")
    def vent(self): print("MOCK: vent()")
    def vent_off(self): print("MOCK: vent_off()")
    def stop(self): print("MOCK: stop()")
    def cleanup(self): print("MOCK: cleanup()")


# ---------------- Factory ---------------- #

def get_esp32_interface(mode, sensors=None):    
    """ Return the appropriate interface implementation. """
    CURRENT_MODE = MODE.get(mode.upper(), MODE["MOCK"])
    logger.info(f"Selected ESP32 interface mode: {CURRENT_MODE}")
    
    if CURRENT_MODE == MODE["GPIO"]:
        return GPIOESP32Interface(sensors=sensors)
    elif CURRENT_MODE == MODE["REST"]:
        logger.info("Using REST API for ESP32 interface")
        return RestESP32Interface(sensors=sensors)
    else:
        return MockESP32Interface()


# ---------------- Manual Test ---------------- #

if __name__ == "__main__":
    ctrl = get_esp32_interface()
    try:
        ctrl.start_gas(); time.sleep(1.5); ctrl.stop_gas()
        ctrl.vent();      time.sleep(1.5); ctrl.vent_off()
        ctrl.stop()
    finally:
        ctrl.cleanup()
