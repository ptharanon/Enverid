# Live Log Implementation

## Overview
Implemented a real-time live log system to display important test updates in the web interface.

## Components Added

### 1. Live Log Module (`live_log.py`)
- Thread-safe in-memory log storage
- Stores last 100 messages by default
- Sequential numbering for efficient polling
- Supports log levels: `info`, `success`, `warning`, `error`
- Can include additional details dictionary with each message

**Key Methods:**
- `add(message, level, details)` - Add log message
- `get_recent(since_sequence, limit)` - Get new messages since last poll
- `get_last_sequence()` - Get current sequence number
- `clear()` - Clear all messages

### 2. Backend API Endpoints (`app.py`)

**New Endpoints:**
- `GET /api/logs` - Fetch recent log messages
  - Query params: `since` (sequence), `limit` (max messages)
  - Returns: `{messages: [...], last_sequence: int}`
  
- `POST /api/logs/clear` - Clear all log messages

### 3. Frontend Updates (`static/js/app.js`)

**New Features:**
- Automatic log polling every 1 second
- Tracks last sequence number to fetch only new messages
- Auto-scrolls log panel to bottom
- Shows message details as tooltip on hover
- Clear button now clears backend logs too

### 4. Cycle Manager Integration (`cycle_manager.py`)

**Log Events Added:**

**Test Lifecycle:**
- Test start with configuration
- Test completion (success/failure)
- Test pause/resume
- Critical errors

**Cycle Events:**
- Cycle start: "Starting Cycle X of Y"
- Cycle completion: "Cycle X completed successfully"

**Stage Events:**
- Stage start with details (duration, fan voltage, heater status)
- Stage completion
- Stage failure

**ESP32 Communication:**
- Command sent successfully with response time
- Command failure with error details
- Connection errors

### 5. Manual Control Integration (`app.py`)

**Manual Command Logging:**
- Command parameters (fan voltage, heater status)
- Command success/failure
- Response time
- Error messages

## Log Levels & Colors

The system uses color-coded log levels:

| Level | Color | Usage |
|-------|-------|-------|
| `info` | Blue (#9cdcfe) | General information, state changes |
| `success` | Green (#4ec9b0) | Successful operations, completions |
| `warning` | Yellow (#dcdcaa) | Warnings, stops, pauses |
| `error` | Red (#f48771) | Failures, connection errors |

## Example Log Messages

### Test Lifecycle
```
[10:23:45] Starting test: Test_20251019_102345
[10:23:45] Test configured: 3 cycles
[10:45:12] Test completed - All 3 cycles successful
```

### Cycle Execution
```
[10:24:01] Starting Cycle 1 of 3
[10:24:02] Stage SCRUB starting - 5 min
[10:24:03] ESP32 command sent successfully to SCRUB
[10:29:04] Stage SCRUB completed successfully
[10:29:05] Stage REGEN starting - 5 min
[10:29:06] ESP32 command sent successfully to REGEN
```

### Errors
```
[10:30:15] ESP32 command failed: Connection timeout
[10:30:15] Stage REGEN failed - ESP32 command error
[10:30:15] Test stopped or failed
```

### Manual Commands
```
[11:15:30] Manual command: Fan 5.0V, Heater ON
[11:15:31] Manual command sent successfully
```

## Usage

### Frontend
The live log automatically polls for updates when on the Auto or Manual pages. No additional code needed - just ensure the Flask server is running.

### Adding New Log Messages (Backend)
```python
from live_log import live_log

# Simple message
live_log.add("Operation completed", level='success')

# Message with details
live_log.add(
    "ESP32 command sent",
    level='info',
    details={'response_time_ms': 145, 'stage': 'REGEN'}
)
```

## Technical Details

### Thread Safety
- Uses `threading.Lock()` to protect shared state
- Safe for concurrent access from Flask request threads and test execution thread

### Memory Management
- Uses `collections.deque` with `maxlen=100`
- Automatically drops oldest messages when full
- Minimal memory footprint

### Polling Efficiency
- Frontend tracks last sequence number
- Only fetches new messages since last poll
- Reduces network traffic and processing
- 1-second poll interval balances responsiveness and load

### Message Details
- Optional `details` dictionary for structured data
- Displayed as tooltip on hover in UI
- Useful for debugging and detailed information

## Future Enhancements

Possible improvements:
1. Persistent log storage (file or database)
2. Log export functionality (CSV, JSON)
3. Log filtering by level
4. Search functionality
5. Configurable retention period
6. Log rotation for long-running tests
7. WebSocket for real-time push instead of polling
