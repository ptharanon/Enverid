import queue
import logging

logger = logging.getLogger(__name__)

class UIQueue:
    """
    Thread-safe queue for UI <-> backend communication.
    """

    def __init__(self):
        self.queue = queue.Queue()

    def put(self, message):
        try:
            self.queue.put(message, block=False)
            logger.debug(f"UIQueue put: {message}")
        except queue.Full:
            logger.warning("UIQueue is full, dropping message")

    def get(self):
        try:
            return self.queue.get(block=False)
        except queue.Empty:
            return None

