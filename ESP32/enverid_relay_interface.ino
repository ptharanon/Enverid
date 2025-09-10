#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

// -----------------------------
// Network Config (Static IP)
// -----------------------------
const char* WIFI_SSID     = "TP-Link_33FE";
const char* WIFI_PASSWORD = "82250805";

IPAddress local_IP(192, 168, 1, 99);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress dns1(8, 8, 8, 8);

// -----------------------------
// Web Server
// -----------------------------
AsyncWebServer server(80);

// -----------------------------
// Command Queue (Async execution)
// -----------------------------
enum class CommandType : uint8_t {
  START_GAS,
  STOP_GAS,
  START_CIRCULATION,
  STOP_CIRCULATION,
  START_VENT,
  STOP_VENT,
  STOP_ALL,
  CLEANUP
};

struct Command {
  CommandType type;
};

QueueHandle_t cmdQueue;

// -----------------------------
// Relay GPIOs (Active HIGH)
// -----------------------------
constexpr int PIN_CIRCULATION = 17;  // circulation fan
constexpr int PIN_GAS         = 19;  // gas solenoid valve
constexpr int PIN_VENT        = 18;  // vent fan 

inline void relayOn(int pin)  { digitalWrite(pin, HIGH);  }
inline void relayOff(int pin) { digitalWrite(pin, LOW); }

// -----------------------------
// Utility: JSON 200 OK response
// -----------------------------
void sendOkJson(AsyncWebServerRequest* request, const char* command) {
  AsyncResponseStream* res = request->beginResponseStream("application/json");
  res->addHeader("Cache-Control", "no-store");
  res->addHeader("Access-Control-Allow-Origin", "*");
  res->print("{\"status\":\"ok\",\"command\":\"");
  res->print(command);
  res->print("\"}");
  request->send(res);
}

void sendErrorJson(AsyncWebServerRequest* request, uint16_t code, const char* message) {
  AsyncResponseStream* res = request->beginResponseStream("application/json");
  res->addHeader("Cache-Control", "no-store");
  res->addHeader("Access-Control-Allow-Origin", "*");
  res->print("{\"status\":\"error\",\"message\":\"");
  res->print(message);
  res->print("\"}");
  res->setCode(code);
  request->send(res);
}

bool enqueueCommand(CommandType t) {
  Command cmd{ t };
  return xQueueSend(cmdQueue, &cmd, 0) == pdTRUE;
}

// -----------------------------
// Command Handlers
// -----------------------------
void handleStartGas() {
  Serial.println("[CMD] start_gas");
  relayOn(PIN_GAS);
}
void handleStopGas() {
  Serial.println("[CMD] stop_gas");
  relayOff(PIN_GAS);
}

void handleStartCirculation() {
  Serial.println("[CMD] start_circulation");
  relayOn(PIN_CIRCULATION);
}
void handleStopCirculation() {
  Serial.println("[CMD] stop_circulation");
  relayOff(PIN_CIRCULATION);
}

void handleStartVent() {
  Serial.println("[CMD] start_vent");
  relayOn(PIN_VENT);
}
void handleStopVent() {
  Serial.println("[CMD] stop_vent");
  relayOff(PIN_VENT);
}

void handleStopAll() {
  Serial.println("[CMD] stop_all");
  relayOff(PIN_GAS);
  relayOff(PIN_CIRCULATION);
  relayOff(PIN_VENT);
}

void handleCleanup() {
  Serial.println("[CMD] cleanup");
  // Example: ensure all OFF
  handleStopAll();
}

// Worker task: consumes queued commands asynchronously
void commandWorker(void* pv) {
  Command cmd;
  while (true) {
    if (xQueueReceive(cmdQueue, &cmd, portMAX_DELAY) == pdTRUE) {
      switch (cmd.type) {
        case CommandType::START_GAS:  handleStartGas();  break;
        case CommandType::STOP_GAS:   handleStopGas();   break;
        case CommandType::START_CIRCULATION: handleStartCirculation(); break;
        case CommandType::STOP_CIRCULATION:  handleStopCirculation();  break;
        case CommandType::START_VENT: handleStartVent(); break;
        case CommandType::STOP_VENT:  handleStopVent();  break;
        case CommandType::STOP_ALL:   handleStopAll();   break;
        case CommandType::CLEANUP:    handleCleanup();   break;
      }
    }
  }
}

// -----------------------------
// Routes
// -----------------------------
void registerRoutes() {
  server.on("/health", HTTP_GET, [](AsyncWebServerRequest* request) {
    sendOkJson(request, "health");
  });

  server.on("/command/start_gas", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::START_GAS)) sendOkJson(request, "start_gas");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/stop_gas", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::STOP_GAS)) sendOkJson(request, "stop_gas");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/start_circulation", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::START_CIRCULATION)) sendOkJson(request, "start_circulation");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/stop_circulation", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::STOP_CIRCULATION)) sendOkJson(request, "stop_circulation");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/start_vent", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::START_VENT)) sendOkJson(request, "start_vent");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/stop_vent", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::STOP_VENT)) sendOkJson(request, "stop_vent");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/stop", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::STOP_ALL)) sendOkJson(request, "stop");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.on("/command/cleanup", HTTP_GET, [](AsyncWebServerRequest* request) {
    if (enqueueCommand(CommandType::CLEANUP)) sendOkJson(request, "cleanup");
    else sendErrorJson(request, 503, "queue_full");
  });

  server.onNotFound([](AsyncWebServerRequest* request) {
    sendErrorJson(request, 404, "not_found");
  });
}

// -----------------------------
// Wi-Fi Connection
// -----------------------------
bool connectWiFi() {
  Serial.print("Configuring static IP... ");
  if (!WiFi.config(local_IP, gateway, subnet, dns1)) {
    Serial.println("FAILED (WiFi.config).");
    return false;
  }
  Serial.println("OK");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 15000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected. IP: ");
    Serial.println(WiFi.localIP());
    return true;
  } else {
    Serial.println("WiFi connect timeout.");
    return false;
  }
}

// -----------------------------
// Setup & Loop
// -----------------------------
void setup() {
  Serial.begin(115200);
  delay(200);

  // Init GPIOs
  pinMode(PIN_CIRCULATION, OUTPUT);
  pinMode(PIN_GAS, OUTPUT);
  pinMode(PIN_VENT, OUTPUT);

  relayOff(PIN_CIRCULATION);
  relayOff(PIN_GAS);
  relayOff(PIN_VENT);

  // Create command queue
  cmdQueue = xQueueCreate(10, sizeof(Command));
  if (!cmdQueue) {
    Serial.println("FATAL: Failed to create command queue");
    while (true) {
      delay(1000);  // Delay 1s before restarting
      ESP.restart(); 
    }
  }

  // Start worker task on core 1
  xTaskCreatePinnedToCore(
    commandWorker, "cmd_worker", 4096, nullptr, 1, nullptr, 1
  );

  if (!connectWiFi()) {
    Serial.println("WARNING: WiFi not connected. Server will start anyway (won't be reachable).");
  }

  registerRoutes();
  server.begin();
  Serial.println("Async server started on http://192.168.1.99");
}

void loop() {
  // Nothing to do — everything is async.
}
