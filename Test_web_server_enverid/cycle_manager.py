"""
Cycle Manager for orchestrating test cycles
Manages: IDLE -> SCRUB -> REGEN -> COOLDOWN -> IDLE
"""

import time
import threading
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from esp32_client import ESP32Client, ESP32CommandBuilder
from database import TestDatabase
from config import config


class CycleManager:
    """Manages cyclic test execution"""
    
    STAGE_ORDER = ['idle', 'scrub', 'regen', 'cooldown']
    
    def __init__(self, esp32_client: ESP32Client, database: TestDatabase):
        self.client = esp32_client
        self.db = database
        
        # Current state
        self.is_running = False
        self.is_paused = False
        self.current_test_run_id = None
        self.current_cycle = 0
        self.current_stage = None
        self.stage_start_time = None
        self.stage_end_time = None
        
        # Configuration
        self.test_config = {}
        self.total_cycles = 0
        
        # Thread control
        self.thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        # Callbacks for status updates
        self.status_callback = None
        
    def configure_test(self, regen_config: Dict, scrub_config: Dict,
                      cooldown_config: Dict, idle_config: Dict,
                      num_cycles: int) -> Dict:
        """
        Configure test parameters matching web UI format
        
        Args:
            regen_config: {fan_volt, heater_temp, duration}
            scrub_config: {fan_volt, duration}
            cooldown_config: {fan_volt, duration}
            idle_config: {duration}
            num_cycles: Number of complete cycles
        """
        self.test_config = {
            'regen': regen_config,
            'scrub': scrub_config,
            'cooldown': cooldown_config,
            'idle': idle_config
        }
        self.total_cycles = num_cycles
        
        return self.test_config
    
    def start_test(self, test_name: str = None) -> bool:
        """Start the cyclic test"""
        if self.is_running:
            return False
        
        if not test_name:
            test_name = f"Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Check ESP32 connection
        if not self.client.check_connection():
            print("ERROR: Cannot connect to ESP32")
            return False
        
        # Create test run in database
        self.current_test_run_id = self.db.create_test_run(
            name=test_name,
            total_cycles=self.total_cycles,
            config=self.test_config
        )
        
        # Reset state
        self.current_cycle = 0
        self.stop_event.clear()
        self.pause_event.clear()
        self.is_running = True
        self.is_paused = False
        
        # Start execution thread
        self.thread = threading.Thread(target=self._run_cycles, daemon=True)
        self.thread.start()
        
        return True
    
    def stop_test(self):
        """Stop the current test"""
        if not self.is_running:
            return
        
        self.stop_event.set()
        self.is_running = False
        
        if self.current_test_run_id:
            self.db.update_test_run(
                self.current_test_run_id,
                end_time=datetime.now(),
                status='stopped',
                completed_cycles=self.current_cycle
            )
        
        # Send emergency stop to ESP32 (transition to IDLE)
        self._send_command('idle', 0)
    
    def pause_test(self):
        """Pause the current test"""
        if self.is_running and not self.is_paused:
            self.pause_event.set()
            self.is_paused = True
    
    def resume_test(self):
        """Resume paused test"""
        if self.is_running and self.is_paused:
            self.pause_event.clear()
            self.is_paused = False
    
    def get_status(self) -> Dict:
        """Get current test status"""
        status = {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'test_run_id': self.current_test_run_id,
            'current_cycle': self.current_cycle,
            'total_cycles': self.total_cycles,
            'current_stage': self.current_stage,
            'stage_start_time': self.stage_start_time.isoformat() if self.stage_start_time else None,
            'stage_end_time': self.stage_end_time.isoformat() if self.stage_end_time else None,
        }
        
        # Calculate time remaining
        if self.stage_end_time and self.is_running and not self.is_paused:
            now = datetime.now()
            if now < self.stage_end_time:
                remaining = (self.stage_end_time - now).total_seconds()
                status['time_remaining_sec'] = int(remaining)
            else:
                status['time_remaining_sec'] = 0
        else:
            status['time_remaining_sec'] = None
        
        return status
    
    def set_status_callback(self, callback: Callable):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def _notify_status(self):
        """Notify status update via callback"""
        if self.status_callback:
            try:
                self.status_callback(self.get_status())
            except Exception as e:
                print(f"Error in status callback: {e}")
    
    def _run_cycles(self):
        """Main cycle execution loop (runs in separate thread)"""
        try:
            for cycle_num in range(1, self.total_cycles + 1):
                if self.stop_event.is_set():
                    break
                
                self.current_cycle = cycle_num
                print(f"\n=== Starting Cycle {cycle_num}/{self.total_cycles} ===")
                
                # Execute each stage in order
                for stage in self.STAGE_ORDER:
                    if self.stop_event.is_set():
                        break
                    
                    # Check pause
                    if self.pause_event.is_set():
                        print(f"Test paused at cycle {cycle_num}, stage {stage}")
                        self.pause_event.wait()  # Wait until resumed
                        print("Test resumed")
                    
                    success = self._execute_stage(stage, cycle_num)
                    
                    if not success:
                        print(f"ERROR: Stage {stage} failed. Stopping test.")
                        self.stop_event.set()
                        break
                
                # Update completed cycles
                if not self.stop_event.is_set():
                    self.db.update_test_run(
                        self.current_test_run_id,
                        completed_cycles=cycle_num
                    )
            
            # Test completed
            if not self.stop_event.is_set():
                self.db.update_test_run(
                    self.current_test_run_id,
                    end_time=datetime.now(),
                    status='completed',
                    result_summary='All cycles completed successfully'
                )
                print(f"\n=== Test Completed: {self.total_cycles} cycles ===")
            
        except Exception as e:
            print(f"ERROR in cycle execution: {e}")
            if self.current_test_run_id:
                self.db.update_test_run(
                    self.current_test_run_id,
                    end_time=datetime.now(),
                    status='error',
                    result_summary=f'Error: {str(e)}'
                )
        finally:
            self.is_running = False
            self.is_paused = False
            self._notify_status()
    
    def _execute_stage(self, stage: str, cycle_num: int) -> bool:
        """Execute a single stage"""
        self.current_stage = stage
        stage_config = self.test_config[stage]
        
        print(f"  Executing stage: {stage.upper()}")
        
        # Get duration
        duration_min = stage_config['duration']
        
        # Create cycle execution record
        cycle_execution_id = self.db.create_cycle_execution(
            test_run_id=self.current_test_run_id,
            cycle_number=cycle_num,
            stage=stage,
            expected_duration_sec=duration_min * 60
        )
        
        # Send command to ESP32
        success = self._send_command(stage, cycle_execution_id)
        
        if not success:
            self.db.complete_cycle_execution(cycle_execution_id, status='failed')
            return False
        
        # Set timing
        self.stage_start_time = datetime.now()
        self.stage_end_time = self.stage_start_time + timedelta(minutes=duration_min)
        self._notify_status()
        
        # Wait for stage duration
        print(f"    Duration: {duration_min} minutes")
        print(f"    Fan voltage: {stage_config.get('fan_volt', 0)}V")
        if stage == 'regen':
            heater_temp = stage_config.get('heater_temp', 0)
            print(f"    Heater: {'ON' if heater_temp > 0 else 'OFF'} ({heater_temp}°C)")
        
        # Wait with periodic status updates
        end_time = time.time() + (duration_min * 60)
        while time.time() < end_time:
            if self.stop_event.is_set():
                self.db.complete_cycle_execution(cycle_execution_id, status='stopped')
                return False
            
            # Check pause
            if self.pause_event.is_set():
                self.pause_event.wait()
            
            time.sleep(1)
            
            # Update status every 5 seconds
            if int(time.time()) % 5 == 0:
                self._notify_status()
        
        # Stage completed
        self.db.complete_cycle_execution(cycle_execution_id, status='completed')
        print(f"  Stage {stage.upper()} completed")
        
        return True
    
    def _send_command(self, stage: str, cycle_execution_id: Optional[int] = None) -> bool:
        """Send command to ESP32 for a specific stage"""
        stage_config = self.test_config.get(stage, {})
        
        # Build command based on stage
        if stage == 'regen':
            fan_volt = stage_config.get('fan_volt', 0)
            heater_temp = stage_config.get('heater_temp', 0)
            duration = stage_config.get('duration', 0)
            
            success, response, error, duration_ms = self.client.send_auto_command(
                phase='regen',
                fan_volt=fan_volt,
                heater=heater_temp > 0,
                duration=duration
            )
            
            payload = {
                'phase': 'regen',
                'fan_volt': fan_volt,
                'heater': heater_temp > 0,
                'duration': duration
            }
            
        elif stage == 'scrub':
            fan_volt = stage_config.get('fan_volt', 0)
            duration = stage_config.get('duration', 0)
            
            success, response, error, duration_ms = self.client.send_auto_command(
                phase='scrub',
                fan_volt=fan_volt,
                heater=False,
                duration=duration
            )
            
            payload = {
                'phase': 'scrub',
                'fan_volt': fan_volt,
                'heater': False,
                'duration': duration
            }
            
        elif stage == 'cooldown':
            fan_volt = stage_config.get('fan_volt', 0)
            duration = stage_config.get('duration', 0)
            
            success, response, error, duration_ms = self.client.send_auto_command(
                phase='cooldown',
                fan_volt=fan_volt,
                heater=False,
                duration=duration
            )
            
            payload = {
                'phase': 'cooldown',
                'fan_volt': fan_volt,
                'heater': False,
                'duration': duration
            }
            
        elif stage == 'idle':
            duration = stage_config.get('duration', 0)
            
            success, response, error, duration_ms = self.client.send_auto_command(
                phase='idle',
                fan_volt=0,
                heater=False,
                duration=duration
            )
            
            payload = {
                'phase': 'idle',
                'fan_volt': 0,
                'heater': False,
                'duration': duration
            }
        else:
            print(f"Unknown stage: {stage}")
            return False
        
        # Log command to database
        self.db.log_esp32_command(
            endpoint='/auto',
            method='POST',
            payload=payload,
            response_status=200 if success else None,
            response_body=str(response),
            error=error,
            duration_ms=duration_ms,
            test_run_id=self.current_test_run_id,
            cycle_execution_id=cycle_execution_id
        )
        
        if not success:
            print(f"    ERROR: {error}")
            return False
        
        print(f"    ESP32 response: {response}")
        return True
