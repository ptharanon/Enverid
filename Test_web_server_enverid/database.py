"""
Database module for logging test runs and ESP32 interactions
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class TestDatabase:
    def __init__(self, db_path: str = 'test_results.db'):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Test runs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL,
                    total_cycles INTEGER,
                    completed_cycles INTEGER DEFAULT 0,
                    config TEXT NOT NULL,
                    result_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Cycle executions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cycle_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_run_id INTEGER NOT NULL,
                    cycle_number INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    expected_duration_sec INTEGER,
                    actual_duration_sec INTEGER,
                    status TEXT NOT NULL,
                    FOREIGN KEY (test_run_id) REFERENCES test_runs(id)
                )
            ''')
            
            # ESP32 commands table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS esp32_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_run_id INTEGER,
                    cycle_execution_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    response_status INTEGER,
                    response_body TEXT,
                    error TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY (test_run_id) REFERENCES test_runs(id),
                    FOREIGN KEY (cycle_execution_id) REFERENCES cycle_executions(id)
                )
            ''')
            
            # Test scenarios table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_run_id INTEGER NOT NULL,
                    scenario_name TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    expected_result TEXT,
                    actual_result TEXT,
                    passed BOOLEAN,
                    error_message TEXT,
                    FOREIGN KEY (test_run_id) REFERENCES test_runs(id)
                )
            ''')
            
            conn.commit()
    
    # ===== TEST RUN METHODS =====
    
    def create_test_run(self, name: str, total_cycles: int, config: Dict) -> int:
        """Create a new test run"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO test_runs (name, start_time, status, total_cycles, config)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, datetime.now(), 'running', total_cycles, json.dumps(config)))
            return cursor.lastrowid
    
    def update_test_run(self, test_run_id: int, **kwargs):
        """Update test run fields"""
        allowed_fields = ['end_time', 'status', 'completed_cycles', 'result_summary']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return
        
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [test_run_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE test_runs SET {set_clause} WHERE id = ?
            ''', values)
    
    def get_test_run(self, test_run_id: int) -> Optional[Dict]:
        """Get test run by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM test_runs WHERE id = ?', (test_run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_test_runs(self, limit: int = 50) -> List[Dict]:
        """Get all test runs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM test_runs 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== CYCLE EXECUTION METHODS =====
    
    def create_cycle_execution(self, test_run_id: int, cycle_number: int, 
                              stage: str, expected_duration_sec: int) -> int:
        """Create a new cycle execution record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cycle_executions 
                (test_run_id, cycle_number, stage, start_time, expected_duration_sec, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (test_run_id, cycle_number, stage, datetime.now(), expected_duration_sec, 'running'))
            return cursor.lastrowid
    
    def complete_cycle_execution(self, cycle_execution_id: int, status: str = 'completed'):
        """Mark cycle execution as complete"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get start time
            cursor.execute('''
                SELECT start_time FROM cycle_executions WHERE id = ?
            ''', (cycle_execution_id,))
            row = cursor.fetchone()
            
            if row:
                start_time = datetime.fromisoformat(row['start_time'])
                end_time = datetime.now()
                actual_duration = int((end_time - start_time).total_seconds())
                
                cursor.execute('''
                    UPDATE cycle_executions 
                    SET end_time = ?, actual_duration_sec = ?, status = ?
                    WHERE id = ?
                ''', (end_time, actual_duration, status, cycle_execution_id))
    
    def get_cycle_executions(self, test_run_id: int) -> List[Dict]:
        """Get all cycle executions for a test run"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM cycle_executions 
                WHERE test_run_id = ? 
                ORDER BY cycle_number, start_time
            ''', (test_run_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== ESP32 COMMAND METHODS =====
    
    def log_esp32_command(self, endpoint: str, method: str, payload: Dict,
                         response_status: Optional[int] = None,
                         response_body: Optional[str] = None,
                         error: Optional[str] = None,
                         duration_ms: Optional[int] = None,
                         test_run_id: Optional[int] = None,
                         cycle_execution_id: Optional[int] = None) -> int:
        """Log an ESP32 command"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO esp32_commands 
                (test_run_id, cycle_execution_id, endpoint, method, payload, 
                 response_status, response_body, error, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (test_run_id, cycle_execution_id, endpoint, method, 
                  json.dumps(payload), response_status, response_body, error, duration_ms))
            return cursor.lastrowid
    
    def get_esp32_commands(self, test_run_id: Optional[int] = None, 
                          cycle_execution_id: Optional[int] = None,
                          limit: int = 100) -> List[Dict]:
        """Get ESP32 commands"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM esp32_commands WHERE 1=1'
            params = []
            
            if test_run_id is not None:
                query += ' AND test_run_id = ?'
                params.append(test_run_id)
            
            if cycle_execution_id is not None:
                query += ' AND cycle_execution_id = ?'
                params.append(cycle_execution_id)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== TEST SCENARIO METHODS =====
    
    def create_test_scenario(self, test_run_id: int, scenario_name: str,
                            scenario_type: str, expected_result: str) -> int:
        """Create a test scenario record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO test_scenarios 
                (test_run_id, scenario_name, scenario_type, start_time, expected_result)
                VALUES (?, ?, ?, ?, ?)
            ''', (test_run_id, scenario_name, scenario_type, datetime.now(), expected_result))
            return cursor.lastrowid
    
    def complete_test_scenario(self, scenario_id: int, actual_result: str,
                              passed: bool, error_message: Optional[str] = None):
        """Complete a test scenario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE test_scenarios 
                SET end_time = ?, actual_result = ?, passed = ?, error_message = ?
                WHERE id = ?
            ''', (datetime.now(), actual_result, passed, error_message, scenario_id))
    
    def get_test_scenarios(self, test_run_id: int) -> List[Dict]:
        """Get all test scenarios for a test run"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM test_scenarios 
                WHERE test_run_id = ? 
                ORDER BY start_time
            ''', (test_run_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== STATISTICS & REPORTING =====
    
    def get_test_run_statistics(self, test_run_id: int) -> Dict:
        """Get comprehensive statistics for a test run"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total commands
            cursor.execute('''
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN response_status BETWEEN 200 AND 299 THEN 1 ELSE 0 END) as successful,
                       SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as errors,
                       AVG(duration_ms) as avg_duration_ms
                FROM esp32_commands 
                WHERE test_run_id = ?
            ''', (test_run_id,))
            command_stats = dict(cursor.fetchone())
            
            # Cycle stats
            cursor.execute('''
                SELECT COUNT(*) as total_stages,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_stages,
                       AVG(actual_duration_sec) as avg_stage_duration_sec
                FROM cycle_executions 
                WHERE test_run_id = ?
            ''', (test_run_id,))
            cycle_stats = dict(cursor.fetchone())
            
            # Test scenario stats
            cursor.execute('''
                SELECT COUNT(*) as total_scenarios,
                       SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_scenarios,
                       SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed_scenarios
                FROM test_scenarios 
                WHERE test_run_id = ?
            ''', (test_run_id,))
            scenario_stats = dict(cursor.fetchone())
            
            return {
                'commands': command_stats,
                'cycles': cycle_stats,
                'scenarios': scenario_stats
            }
