import os, sqlite3, threading, queue
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "sensors.db"

# Global DB queue (batched, thread-safe)
db_queue = queue.Queue()

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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id INTEGER NOT NULL,
        value REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS calibration_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id INTEGER NOT NULL,
        baseline_avg REAL,
        exposure_avg REAL,
        vented_avg REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def _insert_sensor_data_batch(readings):
    """readings: list[(sensor_id:int, value:float)]"""
    if not readings:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO sensor_data (sensor_id, value) VALUES (?, ?)",
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
    """Consume db_queue messages:
       - {"type":"sensor_batch","readings":[(sid,val),...]}
       - {"type":"collection_complete","sensor_id":int,"baseline":float,"exposure":float,"vented":float}
       - {"type":"stop"}  -> clean shutdown
    """
    while True:
        msg = db_queue.get()
        try:
            if msg is None or msg.get("type") == "stop":
                break
            if msg["type"] == "sensor_batch":
                _insert_sensor_data_batch(msg["readings"])
            elif msg["type"] == "collection_complete":
                _insert_calibration_record(
                    msg["sensor_id"], msg["baseline"], msg["exposure"], msg["vented"]
                )
        finally:
            db_queue.task_done()

def start_db_worker():
    t = threading.Thread(target=db_worker, daemon=True)
    t.start()
    return t
