from .db import SessionLocal
from .models import SensorData
import threading, queue

db_queue = queue.Queue()

def log_data_batch(readings):
    db = SessionLocal()
    try:
        for sensor_id, value in readings:
            db.add(SensorData(sensor_id=sensor_id, value=value))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[DB ERROR] {e}")
    finally:
        db.close()

def db_worker():
    while True:
        batch_readings = db_queue.get()
        if batch_readings is None:
            break  # stop signal
        log_data_batch(batch_readings)
        db_queue.task_done()

threading.Thread(target=db_worker, daemon=True).start()
