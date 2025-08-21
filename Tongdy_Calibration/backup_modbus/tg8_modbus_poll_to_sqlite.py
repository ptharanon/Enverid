#!/usr/bin/env python3
"""
TG8 Modbus RTU multi-device polling to SQLite (open/close each cycle)
-------------------------------------------------------------------
- Polls multiple Tongdy TG8 CO2/Temp/Humidity transmitters over RS-485 (Modbus RTU)
- Opens the serial port, polls all devices, then closes the port every cycle
- Stores readings in a local SQLite database

Dependencies:
    pip install pymodbus pyserial
"""

import argparse
import logging
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# ---- Default TG8 register map (adjust if your unit differs) ----
CO2_REG = 0x0000      # CO2 in ppm (unsigned int)
TEMP_REG = 0x0001     # Temperature in 0.1 °C (e.g., 234 -> 23.4°C)
RH_REG = 0x0002       # Relative humidity in 0.1 %RH (e.g., 503 -> 50.3%)

TEMP_SCALE = 0.1
RH_SCALE = 0.1

_shutdown = False

def handle_shutdown(signum, frame):
    global _shutdown
    _shutdown = True

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, handle_shutdown)

def setup_logger(verbosity: int):
    lvl = logging.WARNING
    if verbosity == 1:
        lvl = logging.INFO
    elif verbosity >= 2:
        lvl = logging.DEBUG
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def ensure_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            device_id INTEGER NOT NULL,
            co2_ppm INTEGER,
            temp_c REAL,
            rh_percent REAL
        );
    """)
    conn.commit()

def insert_reading(conn: sqlite3.Connection, device_id: int, co2, temp_c, rh):
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO readings (ts_utc, device_id, co2_ppm, temp_c, rh_percent) VALUES (?, ?, ?, ?, ?)",
        (ts, device_id, co2, temp_c, rh),
    )
    conn.commit()

def read_block(client: ModbusSerialClient, device_id: int, start: int, count: int, timeout_s: float, retries: int):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.read_holding_registers(start, count, slave=device_id)
            if hasattr(resp, "isError") and resp.isError():
                last_err = resp
                time.sleep(0.05 * attempt)
                continue
            return resp.registers
        except ModbusException as e:
            last_err = e
            time.sleep(0.1 * attempt)
        except Exception as e:
            last_err = e
            time.sleep(0.1 * attempt)
    raise RuntimeError(f"Failed to read registers from device {device_id}: {last_err}")

def poll_once(client: ModbusSerialClient, device_id: int, timeout_s: float, retries: int):
    start = min(CO2_REG, TEMP_REG, RH_REG)
    end = max(CO2_REG, TEMP_REG, RH_REG)
    count = (end - start) + 1
    regs = read_block(client, device_id, start, count, timeout_s, retries)

    def regval(addr: int) -> int:
        return regs[addr - start]

    co2_raw = regval(CO2_REG)
    temp_raw = regval(TEMP_REG)
    rh_raw = regval(RH_REG)

    co2_ppm = int(co2_raw)
    temp_c = round(temp_raw * TEMP_SCALE, 2)
    rh_percent = round(rh_raw * RH_SCALE, 2)

    return co2_ppm, temp_c, rh_percent

def main():
    parser = argparse.ArgumentParser(description="Poll Tongdy TG8 devices over Modbus RTU and log to SQLite.")
    parser.add_argument("--port", required=True, help="Serial port, e.g., /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baudrate")
    parser.add_argument("--parity", choices=["N","E","O"], default="N", help="Parity")
    parser.add_argument("--stopbits", type=int, choices=[1,2], default=1, help="Stop bits")
    parser.add_argument("--bytesize", type=int, choices=[7,8], default=8, help="Byte size")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial timeout seconds")
    parser.add_argument("--ids", type=int, nargs="+", required=True, help="Modbus device IDs to poll")
    parser.add_argument("--db", default="tg8_readings.sqlite", help="SQLite database path")
    parser.add_argument("--poll-interval", type=float, default=60.0, help="Polling interval seconds")
    parser.add_argument("--retries", type=int, default=3, help="Retries per read")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    args = parser.parse_args()

    setup_logger(args.verbose)

    conn = sqlite3.connect(args.db, timeout=30, isolation_level=None)
    ensure_schema(conn)

    try:
        while not _shutdown:
            loop_start = time.time()

            client = ModbusSerialClient(
                port=args.port,
                baudrate=args.baudrate,
                parity=args.parity,
                stopbits=args.stopbits,
                bytesize=args.bytesize,
                timeout=args.timeout,
            )

            if client.connect():
                for dev_id in args.ids:
                    try:
                        co2_ppm, temp_c, rh_percent = poll_once(client, dev_id, args.timeout, args.retries)
                        insert_reading(conn, dev_id, co2_ppm, temp_c, rh_percent)
                        logging.info("ID %d  CO2=%d ppm  T=%.2f °C  RH=%.2f %%", dev_id, co2_ppm, temp_c, rh_percent)
                    except Exception as e:
                        logging.warning("ID %d read failed: %s", dev_id, e)
                client.close()
            else:
                logging.error("Failed to open serial port %s", args.port)

            elapsed = time.time() - loop_start
            sleep_left = args.poll_interval - elapsed
            if sleep_left > 0:
                end = time.time() + sleep_left
                while not _shutdown and time.time() < end:
                    time.sleep(min(0.2, end - time.time()))
    finally:
        conn.close()
        logging.info("Stopped.")

if __name__ == "__main__":
    main()
