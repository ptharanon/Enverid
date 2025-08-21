# TG8 Modbus RTU → SQLite Logger

This is a ready-to-run Python script for polling multiple **Tongdy TG8** CO₂/Temp/Humidity transmitters over **RS‑485 Modbus RTU** and logging data into **SQLite**.

## 1) Install dependencies
```bash
sudo apt update
sudo apt install -y python3-pip
pip install pymodbus pyserial
```

## 2) Copy files to your Pi
Place `tg8_modbus_poll_to_sqlite.py` anywhere (for example `/home/pi/tg8/`), make it executable:
```bash
chmod +x tg8_modbus_poll_to_sqlite.py
```

## 3) Run it
```bash
python3 tg8_modbus_poll_to_sqlite.py --port /dev/ttyUSB0 --ids 1 2 3 --poll-interval 5 --db ./tg8_readings.sqlite -v
```
Adjust `--ids` to your device addresses.

**Default register map** used by the script (adjust if your TG8 differs):
- CO₂: holding register `0x0000` (ppm)
- Temp: holding register `0x0001` (0.1 °C scaling)
- RH:   holding register `0x0002` (0.1 % scaling)

To change scaling or addresses, edit the constants near the top of the script (`CO2_REG`, `TEMP_REG`, `RH_REG`, `TEMP_SCALE`, `RH_SCALE`).

## 4) Database
The SQLite DB has a table:
```
readings(id, ts_utc, device_id, co2_ppm, temp_c, rh_percent)
```
Query examples:
```sql
-- last 20 rows
SELECT * FROM readings ORDER BY id DESC LIMIT 20;

-- average CO2 by minute (requires SQLite 3.38+ for strftime in UTC)
SELECT substr(ts_utc, 1, 16) AS minute, device_id, avg(co2_ppm)
FROM readings
GROUP BY minute, device_id
ORDER BY minute DESC;
```

## 5) Run as a service (optional)
Edit and install the systemd unit from `tg8-modbus.service`:
```bash
sudo mkdir -p /home/pi/tg8
sudo cp tg8_modbus_poll_to_sqlite.py /home/pi/tg8/
sudo cp tg8-modbus.service /etc/systemd/system/tg8-modbus.service
sudo systemctl daemon-reload
sudo systemctl enable tg8-modbus
sudo systemctl start tg8-modbus
sudo systemctl status tg8-modbus
```

## 6) Troubleshooting
- Check your serial device path: `ls /dev/ttyUSB*`
- Verify baud/parity/stop bits in your TG8 manual; change with `--baudrate`, `--parity`, `--stopbits`.
- If reads intermittently fail, try `--timeout 1.5 --retries 5` and ensure proper RS‑485 termination and biasing.
- Ensure each device has a unique Modbus ID.
- If values look 10× too large/small, adjust `TEMP_SCALE` or `RH_SCALE` accordingly.

## 7) Next ideas
- Add CSV export or push to InfluxDB/Prometheus
- Expose a small HTTP API for Grafana
- Add calibration/diagnostic registers if supported by your TG8
```

