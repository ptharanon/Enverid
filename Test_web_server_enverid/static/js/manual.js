// Manual Control Page JavaScript

let lastLogSequence = 0;
let logInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('sendManualCmd').addEventListener('click', sendManualCommand);
    document.getElementById('clearManualLog').addEventListener('click', clearLog);
    
    // Heater toggle event listener
    const heaterToggle = document.getElementById('manual_heater_toggle');
    heaterToggle.addEventListener('change', function() {
        const label = document.getElementById('manual_heater_label');
        label.textContent = this.checked ? 'ON' : 'OFF';
    });
    
    checkESP32Status();
    setInterval(checkESP32Status, 5000);
    
    // Start live log polling
    startLogPolling();
});

function setManualPreset(fanVolt, heaterOn) {
    document.getElementById('manual_fan_volt').value = fanVolt;
    document.getElementById('manual_heater_toggle').checked = heaterOn;
    document.getElementById('manual_heater_label').textContent = heaterOn ? 'ON' : 'OFF';
}

async function sendManualCommand() {
    const fanVolt = parseFloat(document.getElementById('manual_fan_volt').value);
    const heaterOn = document.getElementById('manual_heater_toggle').checked;
    
    addLog(`Sending command: Fan ${fanVolt}V, Heater ${heaterOn ? 'ON' : 'OFF'}`, 'info');
    
    try {
        const response = await fetch('/api/manual/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fan_volt: fanVolt,
                heater_on: heaterOn
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog(`✓ Success: ${JSON.stringify(data.response)} (${data.duration_ms}ms)`, 'success');
        } else {
            addLog(`✗ Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`✗ Network error: ${error.message}`, 'error');
    }
}

async function checkESP32Status() {
    try {
        const response = await fetch('/api/esp32/check');
        const data = await response.json();
        
        const statusEl = document.getElementById('esp32_status');
        statusEl.textContent = data.connected ? 'Online' : 'Offline';
        statusEl.className = 'status-badge status-' + (data.connected ? 'online' : 'offline');
        
        document.getElementById('sendManualCmd').disabled = !data.connected;
    } catch (error) {
        console.error('Status check error:', error);
    }
}

function addLog(message, type = 'info') {
    const logOutput = document.getElementById('manual_log');
    const timestamp = new Date().toLocaleTimeString();
    const p = document.createElement('p');
    p.className = `log-${type}`;
    p.textContent = `[${timestamp}] ${message}`;
    logOutput.appendChild(p);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function clearLog() {
    if (!confirm('Clear all log messages?')) {
        return;
    }
    
    fetch('/api/logs/clear', {
        method: 'POST'
    })
    .then(() => {
        document.getElementById('manual_log').innerHTML = '<p>Log cleared.</p>';
        lastLogSequence = 0;
    })
    .catch(error => {
        console.error('Error clearing log:', error);
    });
}

function startLogPolling() {
    // Poll for new log messages every 1 second
    logInterval = setInterval(updateLogs, 1000);
}

async function updateLogs() {
    try {
        const response = await fetch(`/api/logs?since=${lastLogSequence}`);
        const data = await response.json();
        
        if (data.messages && data.messages.length > 0) {
            const logOutput = document.getElementById('manual_log');
            
            // Remove initial message if present
            if (logOutput.children.length === 1 && 
                logOutput.children[0].textContent.includes('Log cleared')) {
                logOutput.innerHTML = '';
            }
            
            data.messages.forEach(msg => {
                const timestamp = new Date(msg.timestamp).toLocaleTimeString();
                const p = document.createElement('p');
                p.className = `log-${msg.level}`;
                p.textContent = `[${timestamp}] ${msg.message}`;
                
                // Add details tooltip if present
                if (msg.details && Object.keys(msg.details).length > 0) {
                    p.title = JSON.stringify(msg.details, null, 2);
                }
                
                logOutput.appendChild(p);
            });
            
            // Auto-scroll to bottom
            logOutput.scrollTop = logOutput.scrollHeight;
            
            // Update last sequence
            lastLogSequence = data.last_sequence;
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}
