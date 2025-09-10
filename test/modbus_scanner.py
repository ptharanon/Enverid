import logging
from pymodbus.client import ModbusSerialClient

# Enable debug logging if you want to see raw messages
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.ERROR)  # Change to logging.DEBUG for verbose output

def scan_modbus_rtu(port, baudrate=9600, timeout=0.2):
    """
    Scan for active Modbus RTU devices on the given serial port.
    """
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
        parity="N",
        stopbits=1,
        bytesize=8
    )

    if not client.connect():
        print(f"❌ Could not open port {port}")
        return

    print(f"🔍 Scanning Modbus RTU devices on {port} at {baudrate} baud...\n")

    active_devices = []
    for unit_id in range(1, 248):  # Valid Modbus addresses: 1–247
        try:
            # Read Holding Register 0 (Function Code 0x03)
            result = client.read_holding_registers(address=0, count=1, device_id=unit_id)

            if result is not None and not result.isError():
                print(f"✅ Found device at address {unit_id}")
                active_devices.append(unit_id)
            else:
                print(f"   No response at address {unit_id}")

        except Exception as e:
            print(f"⚠️ Error at address {unit_id}: {e}")

    client.close()

    if active_devices:
        print("\n🎯 Active Modbus devices found:", active_devices)
    else:
        print("\n⚠️ No devices found.")

if __name__ == "__main__":
    scan_modbus_rtu(port="/dev/tty.usbserial-BG00Y792", baudrate=9600)
