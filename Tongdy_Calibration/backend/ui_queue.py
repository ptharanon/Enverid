from queue import Queue

ui_queue = Queue()  # Thread-safe queue for UI updates
# This queue will be used to push data to the UI thread