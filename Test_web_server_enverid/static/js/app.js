// ESP32 Test Server - Main Dashboard JavaScript

let statusInterval = null;
let isTestRunning = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateStatus();
    startStatusPolling();
    updateFormatDisplay();
});

function initializeEventListeners() {
    // Configuration inputs - update format display on change
    document.querySelectorAll('input[type="number"]').forEach(input => {
        input.addEventListener('input', updateFormatDisplay);
    });
    
    // Buttons
    document.getElementById('saveConfigBtn').addEventListener('click', saveConfiguration);
    document.getElementById('startBtn').addEventListener('click', startTest);
    document.getElementById('stopBtn').addEventListener('click', stopTest);
    document.getElementById('pauseBtn').addEventListener('click', pauseTest);
    document.getElementById('resumeBtn').addEventListener('click', resumeTest);
    document.getElementById('clearLogBtn').addEventListener('click', clearLog);
    document.getElementById('runAutomatedTestsBtn').addEventListener('click', runAutomatedTests);
    document.getElementById('exportBtn').addEventListener('click', exportData);
}

function updateFormatDisplay() {
    const regenV = document.getElementById('regen_fan_volt').value;
    const regenT = document.getElementById('regen_heater_temp').value;
    const regenD = document.getElementById('regen_duration').value;
    
    const scrubV = document.getElementById('scrub_fan_volt').value;
    const scrubD = document.getElementById('scrub_duration').value;
    
    const cooldownV = document.getElementById('cooldown_fan_volt').value;
    const cooldownD = document.getElementById('cooldown_duration').value;
    
    const idleD = document.getElementById('idle_duration').value;
    
    document.getElementById('fmt_regen').textContent = `${regenV}v/${regenT}°C/${regenD}m`;
    document.getElementById('fmt_scrub').textContent = `${scrubV}v/${scrubD}m`;
    document.getElementById('fmt_cooldown').textContent = `${cooldownV}v/${cooldownD}m`;
    document.getElementById('fmt_idle').textContent = `${idleD}m`;
}

async function saveConfiguration() {
    const config = getConfiguration();
    
    try {
        const response = await fetch('/api/test/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog('Configuration saved successfully', 'success');
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function startTest() {
    // First save configuration
    const config = getConfiguration();
    
    try {
        // Configure
        let response = await fetch('/api/test/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            const data = await response.json();
            addLog(`Configuration error: ${data.error}`, 'error');
            return;
        }
        
        addLog('Configuration saved', 'info');
        
        // Start test
        response = await fetch('/api/test/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                test_name: `Test_${new Date().toISOString().replace(/[:.]/g, '-')}`
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog(`Test started! Run ID: ${data.test_run_id}`, 'success');
            isTestRunning = true;
            updateButtonStates();
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function stopTest() {
    if (!confirm('Are you sure you want to stop the test?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/test/stop', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog('Test stopped', 'warning');
            isTestRunning = false;
            updateButtonStates();
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function pauseTest() {
    try {
        const response = await fetch('/api/test/pause', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog('Test paused', 'info');
            document.getElementById('pauseBtn').style.display = 'none';
            document.getElementById('resumeBtn').style.display = 'block';
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function resumeTest() {
    try {
        const response = await fetch('/api/test/resume', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog('Test resumed', 'info');
            document.getElementById('pauseBtn').style.display = 'block';
            document.getElementById('resumeBtn').style.display = 'none';
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function runAutomatedTests() {
    if (!confirm('Run automated test suite? This will test all edge cases and may take several minutes.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/test/automated', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addLog('Automated test suite started - check console for progress', 'success');
        } else {
            addLog(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        addLog(`Network error: ${error.message}`, 'error');
    }
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update system status
        const systemStatus = document.getElementById('system_status');
        systemStatus.textContent = data.system.system_status;
        systemStatus.className = 'status-badge status-' + 
            (data.system.esp32_connected ? 'online' : 'offline');
        
        // Update cycle status
        const cycleStatus = data.cycle;
        
        if (cycleStatus.is_running) {
            isTestRunning = true;
            document.getElementById('test_status').textContent = 
                cycleStatus.is_paused ? 'Paused' : 'Running';
            document.getElementById('test_status').className = 
                'status-badge status-' + (cycleStatus.is_paused ? 'paused' : 'running');
            
            document.getElementById('cycle_info').textContent = 
                `${cycleStatus.current_cycle} / ${cycleStatus.total_cycles}`;
            
            document.getElementById('current_stage').textContent = 
                cycleStatus.current_stage || '-';
            
            if (cycleStatus.time_remaining_sec !== null) {
                const minutes = Math.floor(cycleStatus.time_remaining_sec / 60);
                const seconds = cycleStatus.time_remaining_sec % 60;
                document.getElementById('time_remaining').textContent = 
                    `${minutes}:${seconds.toString().padStart(2, '0')}`;
            } else {
                document.getElementById('time_remaining').textContent = '-';
            }
        } else {
            isTestRunning = false;
            document.getElementById('test_status').textContent = 'Idle';
            document.getElementById('test_status').className = 'status-badge';
            document.getElementById('cycle_info').textContent = '0 / 0';
            document.getElementById('current_stage').textContent = '-';
            document.getElementById('time_remaining').textContent = '-';
        }
        
        updateButtonStates();
        
    } catch (error) {
        console.error('Status update error:', error);
    }
}

function updateButtonStates() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const resumeBtn = document.getElementById('resumeBtn');
    
    if (isTestRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        pauseBtn.disabled = false;
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        pauseBtn.disabled = true;
        resumeBtn.style.display = 'none';
        pauseBtn.style.display = 'block';
    }
}

function getConfiguration() {
    return {
        regen_fan_volt: parseFloat(document.getElementById('regen_fan_volt').value),
        regen_heater_temp: parseFloat(document.getElementById('regen_heater_temp').value),
        regen_duration: parseInt(document.getElementById('regen_duration').value),
        scrub_fan_volt: parseFloat(document.getElementById('scrub_fan_volt').value),
        scrub_duration: parseInt(document.getElementById('scrub_duration').value),
        cooldown_fan_volt: parseFloat(document.getElementById('cooldown_fan_volt').value),
        cooldown_duration: parseInt(document.getElementById('cooldown_duration').value),
        idle_duration: parseInt(document.getElementById('idle_duration').value),
        num_cycles: parseInt(document.getElementById('num_cycles').value)
    };
}

function addLog(message, type = 'info') {
    const logOutput = document.getElementById('log_output');
    const timestamp = new Date().toLocaleTimeString();
    const p = document.createElement('p');
    p.className = `log-${type}`;
    p.textContent = `[${timestamp}] ${message}`;
    logOutput.appendChild(p);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function clearLog() {
    document.getElementById('log_output').innerHTML = '';
}

function startStatusPolling() {
    statusInterval = setInterval(updateStatus, 2000); // Poll every 2 seconds
}

function exportData() {
    addLog('Export functionality - TODO: Implement CSV/JSON export', 'info');
}
