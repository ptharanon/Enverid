import logging
import minimalmodbus
import serial
import time
import random
import threading

from .base import BaseSensor

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class RS485BusManager:
    """Manage exclusive access to a physical RS-485 port and enforce an inter-transaction gap.


    Usage:
    with RS485BusManager.access('/dev/ttyUSB0', pre_delay=0.08):
    # perform minimalmodbus transaction


    This ensures only one transaction runs at a time per port and that there is at least
    `pre_delay` seconds between the end of the previous transaction and the start of the next.
    """


    _locks = {}
    _last_access = {}
    _global_lock = threading.Lock()


    @classmethod
    def _ensure_port(cls, port: str):
        with cls._global_lock:
            if port not in cls._locks:
                cls._locks[port] = threading.Lock()
                cls._last_access[port] = 0.0
            return cls._locks[port]


    @classmethod
    def access(cls, port: str, pre_delay: float = 0.08):
        lock = cls._ensure_port(port)

        class _Ctx:
            def __enter__(self_non):
                lock.acquire()
                # Ensure at least `pre_delay` seconds have passed since last access
                now = time.time()
                last = cls._last_access.get(port, 0.0)
                wait = pre_delay - (now - last)
                if wait > 0:
                    time.sleep(wait)
                return self_non

            def __exit__(self_non, exc_type, exc, tb):
                # mark end time and release
                cls._last_access[port] = time.time()
                lock.release()
                # Note: we do NOT sleep after releasing; the next accessor will enforce pre_delay
                return False

        return _Ctx()

class TongdySensor(BaseSensor):
    """
    Tongdy TG9 CO₂ / Temperature / Humidity via USB↔RS485 (Modbus RTU).
    Uses minimalmodbus for a simple RTU client.
    """

    def __init__(self, port="/dev/ttyUSB0", sensor_id=1, slave_address=1, baudrate=19200, timeout=1.5, is_VOC=True, predelay=0.6):
        """
        :param port: Serial device, e.g. /dev/ttyUSB0
        :param slave_address: Modbus address set on the TG9
        :param baudrate: Usually 9600 (check device)
        :param timeout: Serial timeout in seconds
        """

        super().__init__(sensor_id)
        self.phase = "baseline"  # default phase
        self.predelay = predelay
        self.retries = 3
        self.retry_backoff = 0.5
        
        try:
            self.instrument = minimalmodbus.Instrument(port, slave_address)
            self.instrument.serial.baudrate = baudrate
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = timeout
            self.instrument.mode = minimalmodbus.MODE_RTU
            self.instrument.clear_buffers_before_each_transaction = True
            self.instrument.close_port_after_each_call = False

            self.is_VOC = is_VOC
            logger.info(f"TongdySensor connected on {port} (slave={slave_address})")
        except Exception as e:
            logger.exception("Failed to initialize TongdySensor:")
            self.instrument = None

    def set_phase(self, phase: str):
        self.phase = phase

    def read_values(self):
        """
        Returns a dict: {"co2": ppm, "temperature": °C, "humidity": %RH}
        NOTE: Register addresses/scaling must match the TG9 Modbus map.
                - CO2:    ADDR 0 (ppm, int)
                - Temp:   ADDR 4 (°C x10, signed)
                - Hum:    ADDR 6 (%RH x10, unsigned)
        """
        if self.is_VOC:
            ADDR_CO2 = 0
            ADDR_TEMP = 4
            ADDR_HUMID = 6
            FUNCTION_CODE = 4
        else:
            ADDR_CO2 = 0
            ADDR_TEMP = 2
            ADDR_HUMID = 4
            FUNCTION_CODE = 4

        # print(f"Address CO2: {ADDR_CO2}, Address Temp: {ADDR_TEMP}, Address Humid: {ADDR_HUMID}, Function Code: {FUNCTION_CODE}")

        if not self.instrument:
            return {"co2": None, "temperature": None, "humidity": None}

        attempt = 0
        while attempt < self.retries:
            attempt += 1
            try:
                with RS485BusManager.access(self.instrument.serial.port, self.predelay):
                    # To avoid collisions on RS-485 bus if multiple sensors share the same port,
                    # introduce a small random delay before each transaction.

                    co2   = self.instrument.read_float(registeraddress=ADDR_CO2, 
                                                        functioncode=FUNCTION_CODE, 
                                                        number_of_registers=2)
                    temp  = self.instrument.read_float(registeraddress=ADDR_TEMP, 
                                                        functioncode=FUNCTION_CODE, 
                                                        number_of_registers=2)
                    humid = self.instrument.read_float(registeraddress=ADDR_HUMID, 
                                                        functioncode=FUNCTION_CODE, 
                                                        number_of_registers=2)

                # print(f"Reading values for {self.sensor_id}, values :")
                # print(f"CO2: {co2}")
                # print(f"Temp: {temp}")
                # print(f"Humid: {humid}")
                return {
                    "co2": round(co2,0),
                    "temperature": round(temp,2),   
                    "humidity": round(humid,2)
                }
            except Exception as e:
                logger.error(f"Error reading Tongdy TG9: {e}")
                time.sleep(self.retry_backoff)
            
        # all attempts failed
        logger.error("Sensor %s: all %d read attempts failed", self.sensor_id, self.retries)
        return {"sensor_id": self.sensor_id, "co2": None, "temperature": None, "humidity": None}
