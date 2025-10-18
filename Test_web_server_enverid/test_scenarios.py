"""
Automated Test Scenarios for ESP32 Testing
Covers all edge cases and validation logic
"""

from typing import Dict, List
from esp32_client import ESP32Client
from database import TestDatabase
from config import config
import time


class TestScenario:
    """Base class for test scenarios"""
    
    def __init__(self, name: str, description: str, scenario_type: str):
        self.name = name
        self.description = description
        self.scenario_type = scenario_type
        self.passed = False
        self.error_message = None
        self.actual_result = None
        
    def run(self, client: ESP32Client, db: TestDatabase, test_run_id: int) -> bool:
        """Execute the test scenario"""
        raise NotImplementedError


class ValidStateTransitionTest(TestScenario):
    """Test valid state transitions"""
    
    def __init__(self, from_state: str, to_state: str):
        super().__init__(
            name=f"Valid Transition: {from_state} -> {to_state}",
            description=f"Test transition from {from_state} to {to_state}",
            scenario_type="valid_transition"
        )
        self.from_state = from_state
        self.to_state = to_state
    
    def run(self, client: ESP32Client, db: TestDatabase, test_run_id: int) -> bool:
        scenario_id = db.create_test_scenario(
            test_run_id=test_run_id,
            scenario_name=self.name,
            scenario_type=self.scenario_type,
            expected_result="ESP32 accepts transition (HTTP 200)"
        )
        
        try:
            # First, set to from_state
            success1, _, _, _ = client.send_auto_command(
                phase=self.from_state,
                fan_volt=5.0,
                heater=False,
                duration=1
            )
            
            time.sleep(0.5)
            
            # Then transition to to_state
            success2, response, error, _ = client.send_auto_command(
                phase=self.to_state,
                fan_volt=5.0,
                heater=False,
                duration=1
            )
            
            if success2:
                self.passed = True
                self.actual_result = f"Transition accepted: {response}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, True, None
                )
            else:
                self.passed = False
                self.actual_result = f"Transition rejected: {error}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, False, error
                )
            
            return self.passed
            
        except Exception as e:
            self.passed = False
            self.error_message = str(e)
            db.complete_test_scenario(
                scenario_id, f"Exception: {e}", False, str(e)
            )
            return False


class InvalidStateTransitionTest(TestScenario):
    """Test invalid state transitions (should be rejected)"""
    
    def __init__(self, from_state: str, to_state: str):
        super().__init__(
            name=f"Invalid Transition: {from_state} -> {to_state}",
            description=f"Test that {from_state} to {to_state} is rejected",
            scenario_type="invalid_transition"
        )
        self.from_state = from_state
        self.to_state = to_state
    
    def run(self, client: ESP32Client, db: TestDatabase, test_run_id: int) -> bool:
        scenario_id = db.create_test_scenario(
            test_run_id=test_run_id,
            scenario_name=self.name,
            scenario_type=self.scenario_type,
            expected_result="ESP32 rejects transition (HTTP 400)"
        )
        
        try:
            # Set to from_state
            client.send_auto_command(
                phase=self.from_state,
                fan_volt=5.0,
                heater=False,
                duration=1
            )
            
            time.sleep(0.5)
            
            # Attempt invalid transition
            success, response, error, _ = client.send_auto_command(
                phase=self.to_state,
                fan_volt=5.0,
                heater=False,
                duration=1
            )
            
            # Should be rejected (success = False)
            if not success:
                self.passed = True
                self.actual_result = f"Correctly rejected: {error}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, True, None
                )
            else:
                self.passed = False
                self.actual_result = f"ERROR: Accepted invalid transition"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, False,
                    "Invalid transition was accepted"
                )
            
            return self.passed
            
        except Exception as e:
            self.passed = False
            self.error_message = str(e)
            db.complete_test_scenario(
                scenario_id, f"Exception: {e}", False, str(e)
            )
            return False


class ParameterValidationTest(TestScenario):
    """Test parameter validation"""
    
    def __init__(self, param_name: str, invalid_value, expected_behavior: str):
        super().__init__(
            name=f"Invalid {param_name}: {invalid_value}",
            description=f"Test rejection of {param_name}={invalid_value}",
            scenario_type="parameter_validation"
        )
        self.param_name = param_name
        self.invalid_value = invalid_value
        self.expected_behavior = expected_behavior
    
    def run(self, client: ESP32Client, db: TestDatabase, test_run_id: int) -> bool:
        scenario_id = db.create_test_scenario(
            test_run_id=test_run_id,
            scenario_name=self.name,
            scenario_type=self.scenario_type,
            expected_result=self.expected_behavior
        )
        
        try:
            # Build command with invalid parameter
            if self.param_name == 'fan_volt':
                success, response, error, _ = client.send_auto_command(
                    phase='scrub',
                    fan_volt=self.invalid_value,
                    heater=False,
                    duration=1
                )
            elif self.param_name == 'duration':
                success, response, error, _ = client.send_auto_command(
                    phase='scrub',
                    fan_volt=5.0,
                    heater=False,
                    duration=self.invalid_value
                )
            else:
                raise ValueError(f"Unknown parameter: {self.param_name}")
            
            # Should be rejected
            if not success:
                self.passed = True
                self.actual_result = f"Correctly rejected: {error}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, True, None
                )
            else:
                self.passed = False
                self.actual_result = f"ERROR: Accepted invalid value"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, False,
                    "Invalid parameter was accepted"
                )
            
            return self.passed
            
        except Exception as e:
            self.passed = False
            self.error_message = str(e)
            db.complete_test_scenario(
                scenario_id, f"Exception: {e}", False, str(e)
            )
            return False


class ManualModeTest(TestScenario):
    """Test manual mode functionality"""
    
    def __init__(self):
        super().__init__(
            name="Manual Mode Override",
            description="Test entering manual mode from auto mode",
            scenario_type="manual_mode"
        )
    
    def run(self, client: ESP32Client, db: TestDatabase, test_run_id: int) -> bool:
        scenario_id = db.create_test_scenario(
            test_run_id=test_run_id,
            scenario_name=self.name,
            scenario_type=self.scenario_type,
            expected_result="Can enter manual mode from any auto state"
        )
        
        try:
            # Start in scrub mode
            client.send_auto_command('scrub', 5.0, False, 10)
            time.sleep(0.5)
            
            # Enter manual mode
            success, response, error, _ = client.send_manual_command(
                fan_volt=7.0,
                heater=True
            )
            
            if success:
                self.passed = True
                self.actual_result = f"Manual mode accepted: {response}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, True, None
                )
            else:
                self.passed = False
                self.actual_result = f"Manual mode rejected: {error}"
                db.complete_test_scenario(
                    scenario_id, self.actual_result, False, error
                )
            
            return self.passed
            
        except Exception as e:
            self.passed = False
            self.error_message = str(e)
            db.complete_test_scenario(
                scenario_id, f"Exception: {e}", False, str(e)
            )
            return False


class TestSuiteRunner:
    """Runs comprehensive test suite"""
    
    def __init__(self, client: ESP32Client, db: TestDatabase):
        self.client = client
        self.db = db
        self.scenarios = []
        self._build_test_suite()
    
    def _build_test_suite(self):
        """Build comprehensive test suite"""
        
        # Valid state transitions (based on ESP32 code)
        valid_transitions = [
            ('idle', 'scrub'),
            ('scrub', 'regen'),
            ('regen', 'cooldown'),
            ('cooldown', 'idle'),
            ('idle', 'idle'),  # Stay in same state
        ]
        
        for from_state, to_state in valid_transitions:
            self.scenarios.append(
                ValidStateTransitionTest(from_state, to_state)
            )
        
        # Invalid state transitions (should be rejected)
        invalid_transitions = [
            ('idle', 'regen'),      # Skip scrub
            ('idle', 'cooldown'),   # Skip scrub and regen
            ('scrub', 'cooldown'),  # Skip regen
            ('scrub', 'idle'),      # Backward (might be valid, check ESP32)
            ('regen', 'scrub'),     # Backward
            ('cooldown', 'scrub'),  # Backward
        ]
        
        for from_state, to_state in invalid_transitions:
            self.scenarios.append(
                InvalidStateTransitionTest(from_state, to_state)
            )
        
        # Parameter validation tests
        # Fan voltage out of range
        self.scenarios.append(
            ParameterValidationTest('fan_volt', -1.0, 
                                   "Reject negative voltage")
        )
        self.scenarios.append(
            ParameterValidationTest('fan_volt', 11.0, 
                                   "Reject voltage > 10V")
        )
        self.scenarios.append(
            ParameterValidationTest('fan_volt', 15.5, 
                                   "Reject voltage > 10V")
        )
        
        # Duration validation
        self.scenarios.append(
            ParameterValidationTest('duration', -5, 
                                   "Reject negative duration")
        )
        
        # Manual mode test
        self.scenarios.append(ManualModeTest())
    
    def run_all_tests(self, test_name: str = "Automated Test Suite") -> Dict:
        """Run all test scenarios"""
        
        # Create test run
        test_run_id = self.db.create_test_run(
            name=test_name,
            total_cycles=0,
            config={'type': 'automated_test_suite'}
        )
        
        print(f"\n{'='*60}")
        print(f"Running Test Suite: {len(self.scenarios)} scenarios")
        print(f"{'='*60}\n")
        
        passed = 0
        failed = 0
        
        for i, scenario in enumerate(self.scenarios, 1):
            print(f"[{i}/{len(self.scenarios)}] {scenario.name}...")
            
            try:
                result = scenario.run(self.client, self.db, test_run_id)
                
                if result:
                    passed += 1
                    print(f"  ✓ PASSED: {scenario.actual_result}")
                else:
                    failed += 1
                    print(f"  ✗ FAILED: {scenario.actual_result}")
                
                # Small delay between tests
                time.sleep(0.5)
                
            except Exception as e:
                failed += 1
                print(f"  ✗ ERROR: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Test Suite Complete")
        print(f"  Passed: {passed}/{len(self.scenarios)}")
        print(f"  Failed: {failed}/{len(self.scenarios)}")
        print(f"  Success Rate: {(passed/len(self.scenarios)*100):.1f}%")
        print(f"{'='*60}\n")
        
        # Update test run
        summary = f"Passed: {passed}/{len(self.scenarios)}, Failed: {failed}"
        self.db.update_test_run(
            test_run_id,
            status='completed',
            end_time=time.time(),
            result_summary=summary
        )
        
        return {
            'test_run_id': test_run_id,
            'total': len(self.scenarios),
            'passed': passed,
            'failed': failed,
            'success_rate': passed / len(self.scenarios) * 100
        }
