"""
Live Log Manager for real-time test updates
Stores recent log messages in memory for frontend consumption
"""

from datetime import datetime
from typing import List, Dict
from collections import deque
import threading


class LiveLog:
    """Thread-safe live log manager"""
    
    def __init__(self, max_messages: int = 100):
        self.max_messages = max_messages
        self.messages = deque(maxlen=max_messages)
        self.lock = threading.Lock()
        self.sequence = 0
    
    def add(self, message: str, level: str = 'info', details: Dict = None):
        """
        Add a log message
        
        Args:
            message: Log message text
            level: Log level (info, success, warning, error)
            details: Optional dictionary with additional details
        """
        with self.lock:
            self.sequence += 1
            log_entry = {
                'sequence': self.sequence,
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'level': level,
                'details': details or {}
            }
            self.messages.append(log_entry)
    
    def get_recent(self, since_sequence: int = 0, limit: int = 50) -> List[Dict]:
        """
        Get recent log messages
        
        Args:
            since_sequence: Only return messages after this sequence number
            limit: Maximum number of messages to return
        
        Returns:
            List of log entries
        """
        with self.lock:
            # Filter messages newer than since_sequence
            filtered = [msg for msg in self.messages if msg['sequence'] > since_sequence]
            # Return up to limit messages
            return list(filtered[-limit:])
    
    def get_all(self) -> List[Dict]:
        """Get all stored log messages"""
        with self.lock:
            return list(self.messages)
    
    def clear(self):
        """Clear all log messages"""
        with self.lock:
            self.messages.clear()
            self.sequence = 0
    
    def get_last_sequence(self) -> int:
        """Get the sequence number of the most recent message"""
        with self.lock:
            return self.sequence


# Global instance
live_log = LiveLog()
