from abc import ABC, abstractmethod

class BaseSensor(ABC):
    @abstractmethod
    def read_data(self):
        pass

    @abstractmethod
    def calibrate(self):
        pass
