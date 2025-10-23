import logging
from pymodbus.client import ModbusSerialClient

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.ERROR)

def scan_modbus_rtu_single_baudrate(port, baudrate, timeout=0.1, address_range=None):
    if address_range is None:
        address_range = (1, 248)
    
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
        parity="N",
        stopbits=1,
        bytesize=8
    )

    if not client.connect():
        print(f"Could not open port {port} at {baudrate} baud")
        return []

    start_addr, end_addr = address_range
    print(f"Scanning at {baudrate} baud (addresses {start_addr}-{end_addr})...")

    active_devices = []
    for unit_id in range(start_addr, end_addr):
        try:
            # Read Holding Register 0 (Function Code 0x03)
            result = client.read_holding_registers(address=0, count=1, device_id=unit_id)

            if result is not None and not result.isError():
                print(f"Found device at address {unit_id}")
                active_devices.append(unit_id)

        except Exception as e:
            # Silently skip errors during scan
            pass

    client.close()
    return active_devices


def scan_modbus_rtu(port, baudrates=None, timeout=0.1, quick_scan=True):
    # Handle baudrate parameter
    if baudrates is None:
        baudrates = [9600, 19200, 38400, 57600, 115200]
    elif isinstance(baudrates, int):
        baudrates = [baudrates]
    
    # Set address range based on quick_scan
    address_range = (1, 11) if quick_scan else (1, 248)
    
    print(f"Scanning Modbus RTU devices on {port}")
    print(f"Baudrates to scan: {baudrates}")
    print(f"Mode: {'Quick scan (addresses 1-10)' if quick_scan else 'Full scan (addresses 1-247)'}")
    print(f"Timeout: {timeout}s\n")

    all_results = {}
    
    for baudrate in baudrates:
        print(f"\n{'='*60}")
        print(f"Testing baudrate: {baudrate}")
        print(f"{'='*60}")
        
        devices = scan_modbus_rtu_single_baudrate(port, baudrate, timeout, address_range)
        
        if devices:
            all_results[baudrate] = devices
            print(f"Found {len(devices)} device(s) at {baudrate} baud: {devices}")
        else:
            print(f"No devices found at {baudrate} baud")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    if all_results:
        for baudrate, devices in all_results.items():
            print(f"{baudrate} baud: {devices}")
    else:
        print("No devices found at any baudrate.")

if __name__ == "__main__":
    scan_modbus_rtu(port="/dev/tty.usbmodem56D11266251", quick_scan=True)