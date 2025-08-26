import logging
import minimalmodbus
import serial

logger = logging.getLogger(__name__)

class TongdySensor:
    """
    Tongdy TG9 CO₂ / Temperature / Humidity via USB↔RS485 (Modbus RTU).
    Uses minimalmodbus for a simple RTU client.
    """

    def __init__(self, port="/dev/ttyUSB0", slave_address=1, baudrate=9600, timeout=1.5):
        """
        :param port: Serial device, e.g. /dev/ttyUSB0
        :param slave_address: Modbus address set on the TG9
        :param baudrate: Usually 9600 (check device)
        :param timeout: Serial timeout in seconds
        """
        try:
            self.instrument = minimalmodbus.Instrument(port, slave_address)
            self.instrument.serial.baudrate = baudrate
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = timeout
            self.instrument.mode = minimalmodbus.MODE_RTU
            logger.info(f"TongdySensor connected on {port} (slave={slave_address})")
        except Exception as e:
            logger.exception("Failed to initialize TongdySensor:")
            self.instrument = None

    def read_values(self):
        """
        Returns a dict: {"co2": ppm, "temperature": °C, "humidity": %RH}
        NOTE: Register addresses/scaling must match the TG9 Modbus map.
                - CO2:    ADDR 0 (ppm, int)
                - Temp:   ADDR 4 (°C x10, signed)
                - Hum:    ADDR 6 (%RH x10, unsigned)
        """

        ADDR_CO2 = 0
        ADDR_TEMP = 4
        ADDR_HUMID = 6
        FUNCTION_CODE = 4

        if not self.instrument:
            return {"co2": None, "temperature": None, "humidity": None}

        try:
            co2      = self.instrument.read_float(registeraddress=ADDR_CO2, 
                                                  functioncode=FUNCTION_CODE, 
                                                  number_of_registers=2)
            temp  = self.instrument.read_float(registeraddress=ADDR_TEMP, 
                                                  functioncode=FUNCTION_CODE, 
                                                  number_of_registers=2)
            humid    = self.instrument.read_float(registeraddress=ADDR_HUMID, 
                                                  functioncode=FUNCTION_CODE, 
                                                  number_of_registers=2)

            return {
                "co2": round(co2,0),
                "temperature": round(temp,2),   
                "humidity": round(humid,2)
            }
        except Exception as e:
            logger.error(f"Error reading Tongdy TG9: {e}")
            return {"co2": None, "temperature": None, "humidity": None}
