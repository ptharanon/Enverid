import RPi.GPIO as GPIO
import logging
import time

logger = logging.getLogger(__name__)

class ESP32Interface:
    """
    Raspberry Pi relay control (2 channels) with active-LOW logic.
    Gas valve  -> GPIO23
    Vent fan   -> GPIO24
    """

    def __init__(self, gas_pin=23, vent_pin=24):
        self.gas_pin = gas_pin
        self.vent_pin = vent_pin

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Active-LOW relays; HIGH = OFF (safe default)
        GPIO.setup(self.gas_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.vent_pin, GPIO.OUT, initial=GPIO.HIGH)

        logger.info(f"Relay interface ready (gas={self.gas_pin}, vent={self.vent_pin})")

    # Gas control
    def start_gas(self):
        GPIO.output(self.gas_pin, GPIO.LOW)
        logger.info("Gas valve ON")

    def stop_gas(self):
        GPIO.output(self.gas_pin, GPIO.HIGH)
        logger.info("Gas valve OFF")

    # Vent control
    def vent(self):
        GPIO.output(self.vent_pin, GPIO.LOW)
        logger.info("Vent fan ON")

    def stop(self):
        # Stop all (gas off + vent off)
        GPIO.output(self.gas_pin, GPIO.HIGH)
        GPIO.output(self.vent_pin, GPIO.HIGH)
        logger.info("All relays OFF")

    def vent_off(self):
        GPIO.output(self.vent_pin, GPIO.HIGH)
        logger.info("Vent fan OFF")

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleaned up")

if __name__ == "__main__":
    # Simple manual test
    ctrl = ESP32Interface()
    try:
        ctrl.start_gas(); time.sleep(1.5); ctrl.stop_gas()
        ctrl.vent();      time.sleep(1.5); ctrl.vent_off()
        ctrl.stop()
    finally:
        ctrl.cleanup()
