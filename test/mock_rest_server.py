# mock_esp32_server.py
from flask import Flask, jsonify
import logging
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockESP32")

# List of valid commands (same as your ESP32Interface expects)
VALID_COMMANDS = {
    "start_gas",
    "stop_gas",
    "start_vent",
    "stop_vent",
    "stop",
    "cleanup",
}

@app.route("/command/<command>", methods=["GET"])
def handle_command(command):
    logger.info(f"Received command: {command}")

    if command not in VALID_COMMANDS:
        logger.warning(f"Invalid command received: {command}")
        return jsonify({"status": "error", "message": "invalid command"}), 400

    # Simulate occasional failure (e.g. 20% chance)
    if random.random() < 0.2:  
        logger.error(f"Simulated failure for command: {command}")
        return jsonify({"status": "error", "message": "temporary failure"}), 500

    # Otherwise success
    logger.info(f"Command {command} executed successfully.")
    return jsonify({"status": "ok", "command": command}), 200

if __name__ == "__main__":
    # Run on all interfaces, port 5000 (so target_ip_address = http://<pi-ip>:5000)
    app.run(host="0.0.0.0", port=5000, debug=True)
