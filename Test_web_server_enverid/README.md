# ESP32 Test Web Server

A comprehensive test server for validating ESP32 cartridge control system before production deployment. This server mimics the production web interface and provides automated testing for all logic and edge cases.

## 🎯 Features

### Core Functionality
- **Cyclic Test Management**: Automated execution of IDLE → SCRUB → REGEN → COOLDOWN → IDLE cycles
- **Manual Control**: Direct ESP32 command interface for ad-hoc testing
- **Automated Test Suite**: Comprehensive edge case validation
- **Real-time Monitoring**: Live status updates and logging
- **Test History**: SQLite database logging of all tests and commands

### Test Coverage
- ✅ Valid state transitions
- ✅ Invalid state transitions (rejection testing)
- ✅ Parameter validation (voltage, duration, heater)
- ✅ Manual mode override
- ✅ Network timeout handling
- ✅ Edge case scenarios

## 📋 Requirements

- Python 3.7+
- ESP32 with `enverid_fan_control.ino` firmware
- Network connectivity to ESP32

## 🚀 Quick Start

### 1. Installation

```powershell
# Navigate to the project directory
cd Test_web_server_enverid

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file (or edit `config.py` directly):

```ini
# ESP32 Connection
ESP32_IP=172.29.147.180
ESP32_PORT=80
```

### 3. Run the Server

```powershell
python app.py
```

The server will start on `http://localhost:5000`

### 4. Access the Interface

Open your web browser and navigate to:
- **Main Dashboard**: http://localhost:5000
- **Manual Control**: http://localhost:5000/manual
- **Test Results**: http://localhost:5000/results

## 📖 Usage Guide

### Cyclic Test Mode

1. **Configure Test Parameters**:
   - **REGEN MODE**: Set fan voltage (0-10V), heater temperature (>0 = ON), duration (minutes)
   - **SCRUB MODE**: Set fan voltage, duration
   - **COOLDOWN MODE**: Set fan voltage, duration
   - **IDLE MODE**: Set duration
   - **Number of Cycles**: Specify how many complete cycles to run

2. **Save Configuration**: Click "SAVE CYCLIC FORMAT" (optional - auto-saved on start)

3. **Start Test**: Click "Start" button
   - Test will automatically progress through all stages
   - Real-time status updates displayed
   - Logs show each command sent to ESP32

4. **Monitor Progress**:
   - Current cycle and stage displayed
   - Time remaining for current stage
   - Live log of ESP32 responses

5. **Control Test**:
   - **Pause**: Temporarily halt test (can resume later)
   - **Stop**: Emergency stop and return to IDLE

### Manual Control Mode

1. Navigate to **Manual** tab
2. Set fan voltage and heater temperature
3. Click "Send Command" to directly control ESP32
4. Use quick presets for common configurations:
   - Idle (0V, OFF)
   - Fan 5V, Heater OFF
   - Fan 5V, Heater ON
   - Fan 9V, Heater OFF
   - Max Fan, Heater ON

**Note**: Manual commands put ESP32 in MANUAL mode, overriding any automatic cycle.

### Automated Test Suite

Click "Run All Edge Case Tests" to execute:
- ✅ All valid state transitions
- ❌ All invalid state transitions (should be rejected)
- ❌ Out-of-range parameters (should be rejected)
- ✅ Manual mode functionality
- ✅ Network error handling

Results are logged to the database and viewable in the Results page.

## 🧪 Test Scenarios

### Valid Transitions (Should Pass)
- IDLE → SCRUB
- SCRUB → REGEN
- REGEN → COOLDOWN
- COOLDOWN → IDLE
- IDLE → IDLE (stay in state)

### Invalid Transitions (Should Fail)
- IDLE → REGEN (skip SCRUB)
- IDLE → COOLDOWN (skip SCRUB & REGEN)
- SCRUB → COOLDOWN (skip REGEN)
- REGEN → SCRUB (backward)
- COOLDOWN → SCRUB (backward)

### Parameter Validation
- Fan voltage < 0V (reject)
- Fan voltage > 10V (reject)
- Negative duration (reject)
- Heater temperature logic (>0 = ON, 0 = OFF)

## 📊 Database Schema

The test server logs all data to `test_results.db`:

- **test_runs**: Test execution metadata
- **cycle_executions**: Individual stage executions
- **esp32_commands**: All HTTP commands sent to ESP32
- **test_scenarios**: Automated test results

View results through the web interface or query directly:
```powershell
sqlite3 test_results.db "SELECT * FROM test_runs ORDER BY start_time DESC LIMIT 10;"
```

## 🔧 API Endpoints

### Status & Control
- `GET /api/status` - Get current system and test status
- `POST /api/test/configure` - Configure test parameters
- `POST /api/test/start` - Start cyclic test
- `POST /api/test/stop` - Stop current test
- `POST /api/test/pause` - Pause test
- `POST /api/test/resume` - Resume paused test

### Manual Control
- `POST /api/manual/command` - Send manual command to ESP32

### Testing
- `POST /api/test/automated` - Run automated test suite
- `GET /api/esp32/check` - Check ESP32 connection

### Data
- `GET /api/test_runs` - List test runs
- `GET /api/commands/recent` - Recent ESP32 commands

## 🛠️ Troubleshooting

### ESP32 Not Reachable
1. Check IP address in `config.py` or `.env`
2. Verify ESP32 is powered and connected to network
3. Ping ESP32: `ping 172.29.147.180`
4. Check ESP32 serial monitor for connection status

### Invalid State Transition
- ESP32 firmware enforces state machine logic
- Review `isValidTransition()` function in Arduino code
- Check logs for specific rejection reason

### Test Won't Start
- Ensure ESP32 is online (check status indicator)
- Verify configuration parameters are valid
- Check for any running tests (stop first)

### Database Locked
- Close any open SQLite connections
- Delete `test_results.db` to start fresh (will lose history)

## 📁 Project Structure

```
Test_web_server_enverid/
├── app.py                  # Flask application
├── config.py               # Configuration settings
├── database.py             # Database operations
├── esp32_client.py         # ESP32 HTTP client
├── cycle_manager.py        # Cycle orchestration
├── test_scenarios.py       # Automated test suite
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (optional)
├── test_results.db         # SQLite database (auto-created)
├── templates/              # HTML templates
│   ├── index.html
│   ├── manual.html
│   └── results.html
└── static/                 # Static assets
    ├── css/
    │   └── style.css
    └── js/
        ├── app.js
        └── manual.js
```

## 🔐 ESP32 API Reference

### POST /auto
Automatic mode command (state machine controlled)

**Request:**
```json
{
  "phase": "regen|scrub|cooldown|idle",
  "fan_volt": 0.0-10.0,
  "heater": true|false,
  "duration": 0-1440 (minutes)
}
```

**Response:**
```json
{
  "status": "OK",
  "state": "REGEN"
}
```

### POST /manual
Manual mode command (overrides state machine)

**Request:**
```json
{
  "fan_volt": 0.0-10.0,
  "heater": true|false
}
```

**Response:**
```json
{
  "status": "OK",
  "state": "MANUAL"
}
```

## 📝 Notes

- **Heater Logic**: In the web UI, heater temperature > 0 = ON, = 0 = OFF (converted to boolean for ESP32)
- **Duration**: Specified in minutes, converted to milliseconds by ESP32
- **State Machine**: ESP32 enforces valid transitions - invalid requests return HTTP 400
- **Manual Mode**: Can be entered from any state, effectively pauses automatic cycles

## 🎓 Best Practices

1. **Before Production**: Run automated test suite to verify all ESP32 logic
2. **During Development**: Use manual mode to test individual commands
3. **Long Tests**: Use pause/resume for multi-hour tests
4. **Data Analysis**: Export test results for analysis and reporting
5. **Network Issues**: Test server includes retry logic and timeout handling

## 🐛 Known Issues

- Manual mode exit requires sending an /auto command (by design)
- Very short durations (< 1 minute) may not complete before next command
- Database can grow large with many tests - periodic cleanup recommended

## 📄 License

Internal use only - SCG Enverid Project

## 👥 Author

Test server created for ESP32 cartridge control validation

---

**Version**: 1.0.0  
**Last Updated**: October 2025
