"""
ESP32 Test Server - Flask Application
Mimics the production web server interface for testing ESP32
"""

from flask import Flask, render_template, request, jsonify
from esp32_client import ESP32Client
from database import TestDatabase
from cycle_manager import CycleManager
from test_scenarios import TestSuiteRunner
from config import config
import os

app = Flask(__name__)

# Initialize components
db = TestDatabase(config.DATABASE_PATH)
client = ESP32Client()
cycle_manager = CycleManager(client, db)

# Global state
current_status = {
    'system_status': 'Offline',
    'mode': 'idle',
    'esp32_connected': False
}


def update_esp32_status():
    """Check ESP32 connection status"""
    global current_status
    current_status['esp32_connected'] = client.check_connection()
    current_status['system_status'] = 'Online' if current_status['esp32_connected'] else 'Offline'


# ===== WEB ROUTES =====

@app.route('/')
def index():
    """Main dashboard page"""
    update_esp32_status()
    return render_template('index.html', 
                         config=config,
                         status=current_status)


@app.route('/manual')
def manual_control():
    """Manual control page"""
    update_esp32_status()
    return render_template('manual.html',
                         config=config,
                         status=current_status)


@app.route('/results')
def results_page():
    """Test results page"""
    test_runs = db.get_all_test_runs(limit=20)
    return render_template('results.html',
                         test_runs=test_runs)


@app.route('/results/<int:test_run_id>')
def test_run_details(test_run_id):
    """Detailed test run results"""
    test_run = db.get_test_run(test_run_id)
    if not test_run:
        return jsonify({'error': 'Test run not found'}), 404
    
    cycles = db.get_cycle_executions(test_run_id)
    commands = db.get_esp32_commands(test_run_id=test_run_id)
    scenarios = db.get_test_scenarios(test_run_id)
    statistics = db.get_test_run_statistics(test_run_id)
    
    return render_template('test_details.html',
                         test_run=test_run,
                         cycles=cycles,
                         commands=commands,
                         scenarios=scenarios,
                         statistics=statistics)


# ===== API ENDPOINTS =====

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get current system and test status"""
    update_esp32_status()
    
    cycle_status = cycle_manager.get_status()
    
    return jsonify({
        'system': current_status,
        'cycle': cycle_status
    })


@app.route('/api/test/configure', methods=['POST'])
def api_configure_test():
    """Configure test parameters"""
    data = request.json
    
    try:
        regen_config = {
            'fan_volt': float(data.get('regen_fan_volt', 0)),
            'heater_temp': float(data.get('regen_heater_temp', 0)),
            'duration': int(data.get('regen_duration', 5))
        }
        
        scrub_config = {
            'fan_volt': float(data.get('scrub_fan_volt', 9)),
            'duration': int(data.get('scrub_duration', 5))
        }
        
        cooldown_config = {
            'fan_volt': float(data.get('cooldown_fan_volt', 0)),
            'duration': int(data.get('cooldown_duration', 5))
        }
        
        idle_config = {
            'duration': int(data.get('idle_duration', 5))
        }
        
        num_cycles = int(data.get('num_cycles', 1))
        
        # Validate parameters
        if not (0 <= regen_config['fan_volt'] <= config.MAX_FAN_VOLTAGE):
            return jsonify({'error': 'Invalid regen fan voltage'}), 400
        
        if not (0 <= scrub_config['fan_volt'] <= config.MAX_FAN_VOLTAGE):
            return jsonify({'error': 'Invalid scrub fan voltage'}), 400
        
        if not (0 <= cooldown_config['fan_volt'] <= config.MAX_FAN_VOLTAGE):
            return jsonify({'error': 'Invalid cooldown fan voltage'}), 400
        
        if num_cycles < 1 or num_cycles > config.MAX_CYCLES:
            return jsonify({'error': f'Cycles must be 1-{config.MAX_CYCLES}'}), 400
        
        # Configure cycle manager
        test_config = cycle_manager.configure_test(
            regen_config=regen_config,
            scrub_config=scrub_config,
            cooldown_config=cooldown_config,
            idle_config=idle_config,
            num_cycles=num_cycles
        )
        
        return jsonify({
            'status': 'configured',
            'config': test_config,
            'num_cycles': num_cycles
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/test/start', methods=['POST'])
def api_start_test():
    """Start cyclic test"""
    data = request.json
    test_name = data.get('test_name', None)
    
    if cycle_manager.is_running:
        return jsonify({'error': 'Test already running'}), 400
    
    if not current_status['esp32_connected']:
        return jsonify({'error': 'ESP32 not connected'}), 503
    
    success = cycle_manager.start_test(test_name)
    
    if success:
        return jsonify({
            'status': 'started',
            'test_run_id': cycle_manager.current_test_run_id
        })
    else:
        return jsonify({'error': 'Failed to start test'}), 500


@app.route('/api/test/stop', methods=['POST'])
def api_stop_test():
    """Stop current test"""
    if not cycle_manager.is_running:
        return jsonify({'error': 'No test running'}), 400
    
    cycle_manager.stop_test()
    return jsonify({'status': 'stopped'})


@app.route('/api/test/pause', methods=['POST'])
def api_pause_test():
    """Pause current test"""
    if not cycle_manager.is_running:
        return jsonify({'error': 'No test running'}), 400
    
    cycle_manager.pause_test()
    return jsonify({'status': 'paused'})


@app.route('/api/test/resume', methods=['POST'])
def api_resume_test():
    """Resume paused test"""
    if not cycle_manager.is_running:
        return jsonify({'error': 'No test running'}), 400
    
    cycle_manager.resume_test()
    return jsonify({'status': 'resumed'})


@app.route('/api/manual/command', methods=['POST'])
def api_manual_command():
    """Send manual command to ESP32"""
    data = request.json
    
    try:
        fan_volt = float(data.get('fan_volt', 0))
        heater_temp = float(data.get('heater_temp', 0))
        
        # Validate
        if not (0 <= fan_volt <= config.MAX_FAN_VOLTAGE):
            return jsonify({'error': 'Invalid fan voltage'}), 400
        
        # Send command
        success, response, error, duration_ms = client.send_manual_command(
            fan_volt=fan_volt,
            heater=heater_temp > 0
        )
        
        # Log command
        db.log_esp32_command(
            endpoint='/manual',
            method='POST',
            payload={'fan_volt': fan_volt, 'heater': heater_temp > 0},
            response_status=200 if success else None,
            response_body=str(response),
            error=error,
            duration_ms=duration_ms
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'response': response,
                'duration_ms': duration_ms
            })
        else:
            return jsonify({
                'status': 'error',
                'error': error,
                'duration_ms': duration_ms
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/test/automated', methods=['POST'])
def api_run_automated_tests():
    """Run automated test suite"""
    if cycle_manager.is_running:
        return jsonify({'error': 'Cycle test already running'}), 400
    
    if not current_status['esp32_connected']:
        return jsonify({'error': 'ESP32 not connected'}), 503
    
    try:
        # Run test suite in background
        import threading
        
        def run_tests():
            runner = TestSuiteRunner(client, db)
            results = runner.run_all_tests()
            print(f"Automated tests complete: {results}")
        
        thread = threading.Thread(target=run_tests, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Automated test suite started'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/esp32/check', methods=['GET'])
def api_check_esp32():
    """Check ESP32 connection"""
    connected = client.check_connection()
    return jsonify({
        'connected': connected,
        'url': client.base_url
    })


@app.route('/api/commands/recent', methods=['GET'])
def api_recent_commands():
    """Get recent ESP32 commands"""
    limit = request.args.get('limit', 50, type=int)
    commands = db.get_esp32_commands(limit=limit)
    return jsonify(commands)


@app.route('/api/test_runs', methods=['GET'])
def api_test_runs():
    """Get list of test runs"""
    limit = request.args.get('limit', 20, type=int)
    test_runs = db.get_all_test_runs(limit=limit)
    return jsonify(test_runs)


# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ===== STARTUP =====

if __name__ == '__main__':
    print("="*60)
    print("ESP32 Test Server")
    print("="*60)
    print(f"ESP32 Target: {config.ESP32_BASE_URL}")
    print(f"Database: {config.DATABASE_PATH}")
    print(f"Server: http://{config.TEST_SERVER_HOST}:{config.TEST_SERVER_PORT}")
    print("="*60)
    
    # Check ESP32 connection
    print("\nChecking ESP32 connection...")
    if client.check_connection():
        print("ESP32 is reachable")
    else:
        print("ESP32 is NOT reachable - check IP address and network")
    
    print("\nStarting server...\n")
    
    app.run(
        host=config.TEST_SERVER_HOST,
        port=config.TEST_SERVER_PORT,
        debug=config.DEBUG
    )
