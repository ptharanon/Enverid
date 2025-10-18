// Manual Control Page JavaScript

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('sendManualCmd').addEventListener('click', sendManualCommand);
    document.getElementById('clearManualLog').addEventListener('click', clearLog);
    checkESP32Status();
    setInterval(checkESP32Status, 5000);
});

function setManualPreset(fanVolt, heaterTemp) {
    document.getElementById('manual_fan_volt').value = fanVolt;
    document.getElementById('manual_heater_temp').value = heaterTemp;
}

async function sendManualCommand() {
    const fanVolt = parseFloat(document.getElementById('manual_fan_volt').value);
    const heaterTemp = parseFloat(document.getElementById('manual_heater_temp').value);
    
    addLog(`Sending command: Fan ${fanVolt}V, Heater ${heaterTemp > 0 ? 'ON' : 'OFF'} (${heaterTemp}°C)`, 'info');
    
    try {
        const response = await fetch('/api/manual/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fan_volt: fanVolt,
                heater_temp: heaterTemp
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
    document.getElementById('manual_log').innerHTML = '';
}
