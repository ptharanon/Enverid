from abc import ABC, abstractmethod

class BaseSensor(ABC):
    @abstractmethod
    def read_values(self) -> dict:
        """
        Read data from the sensor.
        keys: "co2", "temperature", "humidity"
        """
        raise NotImplementedError

    @abstractmethod
    def set_phase(self):
        """phase in {'baseline','exposure','vented'} (optional)"""
        pass