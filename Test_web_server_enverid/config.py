"""
Configuration for ESP32 Test Server
Matches the web UI format from https://main.d3g148efpb30ht.amplifyapp.com/
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ESP32 Connection
    ESP32_IP = os.getenv('ESP32_IP', '172.29.147.180')
    ESP32_PORT = os.getenv('ESP32_PORT', '80')
    ESP32_BASE_URL = f"http://{ESP32_IP}:{ESP32_PORT}"
    
    # HTTP Settings
    REQUEST_TIMEOUT = 5  # seconds
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 1  # seconds
    
    # Database
    DATABASE_PATH = 'test_results.db'
    
    # Test Server
    TEST_SERVER_HOST = '0.0.0.0'
    TEST_SERVER_PORT = 5000
    DEBUG = True
    
    # Stage Parameters (matching web UI)
    DEFAULT_REGEN = {
        'fan_volt': 0,
        'heater_temp': 0,  # >0 = ON, 0 = OFF
        'duration': 5  # minutes
    }
    
    DEFAULT_SCRUB = {
        'fan_volt': 9,
        'duration': 5  # minutes
    }
    
    DEFAULT_COOLDOWN = {
        'fan_volt': 0,
        'duration': 5  # minutes
    }
    
    DEFAULT_IDLE = {
        'duration': 5  # minutes
    }
    
    DEFAULT_CYCLES = 1
    
    # Validation Limits
    MAX_FAN_VOLTAGE = 10.0
    MIN_FAN_VOLTAGE = 0.0
    MAX_DURATION_MINUTES = 1440  # 24 hours
    MIN_DURATION_MINUTES = 0
    MAX_CYCLES = 100

# Create global config instance
config = Config()
