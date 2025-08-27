import os, sqlite3, threading, queue
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "sensors.db"

db_queue = queue.Queue()


######### DATABASE CURRENT_TIMESTAMP IS IN GMT+0 #########
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        model TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # add metric column so we can store co2/temp/humidity
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id INTEGER NOT NULL,
        metric TEXT NOT NULL,              -- 'co2' | 'temperature' | 'humidity'
        value FLOAT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS calibration_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id INTEGER NOT NULL,
        baseline_avg FLOAT,
        exposure_avg FLOAT,
        vented_avg FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def _insert_sensor_data_batch(readings):
    """
    readings: list[(sensor_id:int, metric:str, value:float)]
    """
    if not readings:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO sensor_data (sensor_id, metric, value) VALUES (?, ?, ?)",
        readings
    )
    conn.commit()
    conn.close()

def _insert_calibration_record(sensor_id, baseline, exposure, vented):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO calibration_sessions (sensor_id, baseline_avg, exposure_avg, vented_avg)
        VALUES (?, ?, ?, ?)
    """, (sensor_id, baseline, exposure, vented))
    conn.commit()
    conn.close()

def db_worker():
    while True:
        msg = db_queue.get()
        try:
            if msg is None or msg.get("type") == "stop":
                break
            if msg["type"] == "sensor_batch":
                _insert_sensor_data_batch(msg["readings"])
            elif msg["type"] == "calibration":
                _insert_calibration_record(
                    msg["sensor_id"], msg["baseline"], msg["exposure"], msg["vented"]
                )
        finally:
            db_queue.task_done()

def start_db_worker():
    t = threading.Thread(target=db_worker, daemon=True)
    t.start()
    return t
