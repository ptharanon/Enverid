from .models import Sensor
from .db import SessionLocal

def add_sensor(name: str, sensor_type: str):
    db = SessionLocal()
    sensor = Sensor(name=name, type=sensor_type)
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    db.close()
    return sensor

def rename_sensor(sensor_id: int, new_name: str):
    db = SessionLocal()
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
    if sensor:
        sensor.name = new_name
        db.commit()
    db.close()
