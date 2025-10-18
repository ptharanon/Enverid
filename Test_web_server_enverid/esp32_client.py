"""
ESP32 Client for HTTP communication
Handles /auto and /manual endpoints
"""

import requests
import time
from typing import Dict, Optional, Tuple
from config import config


class ESP32Client:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.ESP32_BASE_URL
        self.timeout = config.REQUEST_TIMEOUT
        self.retry_attempts = config.RETRY_ATTEMPTS
        self.retry_delay = config.RETRY_DELAY
        
    def _make_request(self, endpoint: str, payload: Dict) -> Tuple[bool, Dict, Optional[str], int]:
        """
        Make HTTP POST request to ESP32
        
        Returns:
            (success, response_data, error_message, duration_ms)
        """
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    return True, response.json(), None, duration_ms
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return False, {}, error_msg, duration_ms
                    
            except requests.exceptions.Timeout:
                error_msg = f"Timeout after {self.timeout}s"
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                duration_ms = int((time.time() - start_time) * 1000)
                return False, {}, error_msg, duration_ms
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                duration_ms = int((time.time() - start_time) * 1000)
                return False, {}, error_msg, duration_ms
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                duration_ms = int((time.time() - start_time) * 1000)
                return False, {}, error_msg, duration_ms
        
        duration_ms = int((time.time() - start_time) * 1000)
        return False, {}, "Max retries exceeded", duration_ms
    
    def send_auto_command(self, phase: str, fan_volt: float, 
                         heater: bool, duration: int) -> Tuple[bool, Dict, Optional[str], int]:
        """
        Send command to /auto endpoint
        
        Args:
            phase: 'idle', 'scrub', 'regen', or 'cooldown'
            fan_volt: Fan voltage 0-10V
            heater: Heater ON/OFF
            duration: Duration in minutes
            
        Returns:
            (success, response_data, error_message, duration_ms)
        """
        # Validate parameters
        if phase not in ['idle', 'scrub', 'regen', 'cooldown']:
            return False, {}, f"Invalid phase: {phase}", 0
        
        if not (0 <= fan_volt <= config.MAX_FAN_VOLTAGE):
            return False, {}, f"Fan voltage must be 0-{config.MAX_FAN_VOLTAGE}V", 0
        
        if duration < 0:
            return False, {}, "Duration must be non-negative", 0
        
        payload = {
            'phase': phase,
            'fan_volt': fan_volt,
            'heater': heater,
            'duration': duration
        }
        
        return self._make_request('/auto', payload)
    
    def send_manual_command(self, fan_volt: float, heater: bool) -> Tuple[bool, Dict, Optional[str], int]:
        """
        Send command to /manual endpoint
        
        Args:
            fan_volt: Fan voltage 0-10V
            heater: Heater ON/OFF
            
        Returns:
            (success, response_data, error_message, duration_ms)
        """
        # Validate parameters
        if not (0 <= fan_volt <= config.MAX_FAN_VOLTAGE):
            return False, {}, f"Fan voltage must be 0-{config.MAX_FAN_VOLTAGE}V", 0
        
        payload = {
            'fan_volt': fan_volt,
            'heater': heater
        }
        
        return self._make_request('/manual', payload)
    
    def check_connection(self) -> bool:
        """Check if ESP32 is reachable"""
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=2
            )
            return response.status_code in [200, 404]  # Any response means it's alive
        except:
            return False


class ESP32CommandBuilder:
    """Helper class to build commands matching the web UI format"""
    
    @staticmethod
    def build_regen_command(fan_volt: float, heater_temp: float, duration: int) -> Dict:
        """
        Build REGEN command
        heater_temp > 0 = ON, heater_temp = 0 = OFF
        """
        return {
            'phase': 'regen',
            'fan_volt': fan_volt,
            'heater': heater_temp > 0,  # Convert temp to boolean
            'duration': duration
        }
    
    @staticmethod
    def build_scrub_command(fan_volt: float, duration: int) -> Dict:
        """Build SCRUB command"""
        return {
            'phase': 'scrub',
            'fan_volt': fan_volt,
            'heater': False,
            'duration': duration
        }
    
    @staticmethod
    def build_cooldown_command(fan_volt: float, duration: int) -> Dict:
        """Build COOLDOWN command"""
        return {
            'phase': 'cooldown',
            'fan_volt': fan_volt,
            'heater': False,
            'duration': duration
        }
    
    @staticmethod
    def build_idle_command(duration: int) -> Dict:
        """Build IDLE command"""
        return {
            'phase': 'idle',
            'fan_volt': 0,
            'heater': False,
            'duration': duration
        }
    
    @staticmethod
    def build_manual_command(fan_volt: float, heater_temp: float) -> Dict:
        """Build MANUAL command"""
        return {
            'fan_volt': fan_volt,
            'heater': heater_temp > 0  # Convert temp to boolean
        }
