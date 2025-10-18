#include <Arduino.h>
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <LiquidCrystal_I2C.h>
#include <AsyncJson.h>
#include <ArduinoJson.h>

bool IS_DEBUG_SERIAL_COMMAND = false;

//-------------------------------------------------
// LINEAR INTERPOLATION TABLES
//-------------------------------------------------
const int NUM_POINTS = 20;
const float percentTable[NUM_POINTS] = {
  5, 10, 15, 20, 25, 30, 35, 40, 45, 50,
  55, 60, 65, 70, 75, 80, 85, 90, 95, 100
};
const float voltageTable[NUM_POINTS] = {
  0.394, 1.176, 1.81, 2.4, 2.97, 3.54, 4.1, 4.65, 5.2, 5.75,
  6.3, 6.84, 7.39, 7.93, 8.46, 9.0, 9.54, 10.1, 10.63, 10.63
};

//------------------------------------------------
// DEFINE PINS / CONSTANTS
//------------------------------------------------
constexpr int PWM_OUT_PIN   = 18;      
constexpr int LEDC_CHANNEL  = 0;
constexpr int PWM_FREQ_HZ   = 2000;    
constexpr int PWM_RES_BITS  = 13;      
constexpr int PWM_MAX       = (1 << PWM_RES_BITS) - 1;

constexpr int LCD_SDA_PIN  = 21;
constexpr int LCD_SCL_PIN  = 22;

constexpr float MAX_VOLTAGE = 10.0f;   // Converter output full-scale

constexpr int PIN_HEATER_RELAY = 19;  // TODO Recheck

//------------------------------------------------
// NETWORK SETTINGS
//------------------------------------------------
const char* WIFI_SSID = "NSTDA-Wifi-IoT";
const char* WIFI_PASSWORD = "abcDEF99";

IPAddress local_IP(172, 29, 147, 180);
IPAddress gateway(172, 29, 147, 1); // Check gateway again
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);


//------------------------------------------------
// WEBSERVER SETTINGS
//------------------------------------------------
AsyncWebServer server(80);

//------------------------------------------------
// SYSTEM STATES
//------------------------------------------------
enum class SystemState: uint8_t {
  IDLE,
  SCRUBBING,
  REGEN,
  COOLDOWN,
  MANUAL
};

// State transition validation
// Valid transitions: IDLE -> SCRUB -> REGEN -> COOLDOWN -> IDLE
// MANUAL can transition to/from any state
bool isValidTransition(SystemState from, SystemState to) {
  // MANUAL mode can be transitioned to/from any state
  if(from == SystemState::MANUAL || to == SystemState::MANUAL) {
    return true;
  }

  switch(from) {
    case SystemState::IDLE:
      return (to == SystemState::SCRUBBING || to == SystemState::IDLE);
      
    case SystemState::SCRUBBING:
      return (to == SystemState::REGEN || to == SystemState::IDLE);
      
    case SystemState::REGEN:
      return (to == SystemState::COOLDOWN || to == SystemState::IDLE);
      
    case SystemState::COOLDOWN:
      return (to == SystemState::IDLE || to == SystemState::COOLDOWN);
      
    case SystemState::MANUAL:
      return true;
      
    default:
      return false;
  }
}

const char* getStateName(SystemState state) {
  switch(state) {
    case SystemState::IDLE: return "IDLE";
    case SystemState::SCRUBBING: return "SCRUBBING";
    case SystemState::REGEN: return "REGEN";
    case SystemState::COOLDOWN: return "COOLDOWN";
    case SystemState::MANUAL: return "MANUAL";
    default: return "UNKNOWN";
  }
}

struct State {
  SystemState state;
  unsigned long duration; // in milliseconds
  float fanVoltage;
  bool heaterOn;
};

QueueHandle_t stateQueue;

bool enqueueState(SystemState state = SystemState::IDLE, unsigned long duration = 0, float fanVoltage = 0.0f, bool heaterOn = false) {
  State newState = { state, duration, fanVoltage, heaterOn };
  return xQueueSend(stateQueue, &newState, 0) == pdTRUE;
}

//------------------------------------------------
// GLOBAL VARIABLES
//------------------------------------------------
SemaphoreHandle_t stateMutex = NULL;
SystemState currentState = SystemState::IDLE;

unsigned long stateStartTime = 0;
unsigned long stateEndTime = 0;

float currentPercent = 0.0f;
float commandedVoltage = 0.0f;
float appliedPWMpercent = 0.0f;


LiquidCrystal_I2C lcd(0x27, 16, 2);   // 16 columns, 2 rows


//------------------------------------------------
// HELPER FUNCTIONS
//------------------------------------------------

// Convert percent (0-100) to PWM duty cycle
inline uint32_t percentToDuty(float percent) {
  percent = constrain(percent, 0.0f, 100.0f);
  return (uint32_t)((percent / 100.0f) * PWM_MAX);
}

// inline float percentToVoltage(float percent) {
//   percent = constrain(percent, 0.0f, 100.0f);
//   return (percent / 100.0f) * MAX_VOLTAGE;
// }

// Linear interpolation functions
float interpolateVoltage(float pct) {
  if (pct <= percentTable[0]) return voltageTable[0];
  if (pct >= percentTable[NUM_POINTS-1]) return voltageTable[NUM_POINTS-1];

  for (int i = 0; i < NUM_POINTS - 1; i++) {
    if (pct >= percentTable[i] && pct <= percentTable[i+1]) {
      float t = (pct - percentTable[i]) / (percentTable[i+1] - percentTable[i]);
      return voltageTable[i] + t * (voltageTable[i+1] - voltageTable[i]);
    }
  }
  return 0; // fallback
}

// Given a desired voltage (0–10 V), find the PWM percent needed
float interpolatePercentForVoltage(float voltage) {
  if (voltage <= voltageTable[0]) return percentTable[0];
  if (voltage >= voltageTable[NUM_POINTS-1]) return percentTable[NUM_POINTS-1];

  for (int i = 0; i < NUM_POINTS - 1; i++) {
    if (voltage >= voltageTable[i] && voltage <= voltageTable[i+1]) {
      float t = (voltage - voltageTable[i]) / (voltageTable[i+1] - voltageTable[i]);
      return percentTable[i] + t * (percentTable[i+1] - percentTable[i]);
    }
  }
  return 0;
}

// Set fan voltage via PWM
bool commandFanVoltage(float voltage) {
  voltage = constrain(voltage, 0.0f, MAX_VOLTAGE);
  float targetPercent = interpolatePercentForVoltage(voltage);
  uint32_t duty = percentToDuty(targetPercent);
  ledcWrite(LEDC_CHANNEL, duty);
  commandedVoltage = voltage;
  appliedPWMpercent = targetPercent;
  return true;
}

// Relay control
inline void relayOn(int pin) {
  digitalWrite(pin, HIGH);
}
inline void relayOff(int pin) {
  digitalWrite(pin, LOW);
}

// Emergency shutdown to IDLE
inline void emergencyShutdown() {
  commandFanVoltage(0.0f);
  relayOff(PIN_HEATER_RELAY);
  
  // Thread-safe state update
  if(xSemaphoreTake(stateMutex, portMAX_DELAY) == pdTRUE) {
    currentState = SystemState::IDLE;
    stateEndTime = 0;
    xSemaphoreGive(stateMutex);
  }
  
  currentPercent = 0.0f;
  commandedVoltage = 0.0f;
  appliedPWMpercent = 0.0f;
}

//------------------------------------------------
// LCD FUNCTIONS
//------------------------------------------------

// TODO Redo the LCD update function to accept various checks
void updateLCD(float cmdPct, float outV) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Cmd: ");
  lcd.print(cmdPct, 1);
  lcd.print("%    ");

  lcd.setCursor(0, 1);
  lcd.print("Out: ");
  lcd.print(outV, 2);
  lcd.print(" V    ");
}

// LCD setup
void setupLCD() {
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.print("Calibrated Ready"); // TODO Change this
  delay(1000);
  lcd.clear();
}

//--------------------------------------------------
// RESPONSE FUNCTIONS
//--------------------------------------------------
void sendOkResponse(AsyncWebServerRequest *request, const char* state) {
  AsyncResponseStream* res = request->beginResponseStream("application/json");
  res -> addHeader("Cache-Control", "no-cache");
  res -> addHeader("Access-Control-Allow-Origin", "*");
  res -> print("{\"status\":\"OK\",\"state\":\"");
  res -> print(state);
  res -> print("\"}");
  request->send(res);
}

void sendErrorResponse(AsyncWebServerRequest *request, uint16_t code, const char* message) {
  AsyncResponseStream* res = request->beginResponseStream("application/json");
  res -> addHeader("Cache-Control", "no-cache");
  res -> addHeader("Access-Control-Allow-Origin", "*");
  res -> print("{\"status\":\"ERROR\",\"message\":\"");
  res -> print(message);
  res -> print("\"}");
  res -> setCode(code);
  request->send(res);
}

//--------------------------------------------------
// HANDLERS
//--------------------------------------------------

// /auto endpoint handler
AsyncCallbackJsonWebHandler* manageAutoHandler = new AsyncCallbackJsonWebHandler("/auto", [](AsyncWebServerRequest *request, JsonVariant &json) {
  if(!json.is<JsonObject>()) {
    sendErrorResponse(request, 400, "Received data is not a JSON object");
    return;
  }  
  JsonObject jsonObj = json.as<JsonObject>();
  
  serializeJsonPretty(jsonObj, Serial); // Debug output

  if(!jsonObj.containsKey("phase") || !jsonObj.containsKey("fan_volt") || 
     !jsonObj.containsKey("heater") || !jsonObj.containsKey("duration")) {
    sendErrorResponse(request, 400, "Missing required fields");
    return;
  }
  
  // Unpack the JSON fields
  const char* phase = jsonObj["phase"];
  float fanVolt = jsonObj["fan_volt"];
  bool heater = jsonObj["heater"];
  int duration = jsonObj["duration"];
  
  // Validate phase
  SystemState targetState;
  if(strcmp(phase, "regen") == 0) {
    targetState = SystemState::REGEN;
  } else if(strcmp(phase, "scrub") == 0) {
    targetState = SystemState::SCRUBBING;
  } else if(strcmp(phase, "idle") == 0) {
    targetState = SystemState::IDLE;
  } else if(strcmp(phase, "cooldown") == 0) {
    targetState = SystemState::COOLDOWN;
  } else {
    sendErrorResponse(request, 400, "Invalid phase value");
    return;
  }
  
  // Validate fan voltage (0-10V)
  if(fanVolt < 0.0f || fanVolt > 10.0f) {
    sendErrorResponse(request, 400, "fan_volt must be between 0 and 10");
    return;
  }
  
  // Validate duration (positive)
  if(duration < 0) {
    sendErrorResponse(request, 400, "duration must be positive");
    return;
  }
  
  // Validate that we're not already in the target state (thread-safe read)
  SystemState localCurrentState;
  if(xSemaphoreTake(stateMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
    localCurrentState = currentState;
    xSemaphoreGive(stateMutex);
  } else {
    sendErrorResponse(request, 500, "Failed to acquire state lock");
    return;
  }
  if(localCurrentState == targetState) {
    sendErrorResponse(request, 400, "Already in the target state");
    return;
  }
  
  // Validate state transition
  if(!isValidTransition(localCurrentState, targetState)) {
    char errorMsg[100];
    snprintf(errorMsg, sizeof(errorMsg), 
             "Invalid transition from %s to %s", 
             getStateName(localCurrentState), 
             getStateName(targetState));
    sendErrorResponse(request, 400, errorMsg);
    return;
  }
  
  // Convert duration from minutes to milliseconds
  unsigned long durationMs = (unsigned long)duration * 60000UL;
  
  if (enqueueState(targetState, durationMs, fanVolt, heater)) {
    sendOkResponse(request, phase);
  } else {
    sendErrorResponse(request, 500, "Failed to enqueue state");
  }
});

// /manual endpoint handler
AsyncCallbackJsonWebHandler* manageManualHandler = new AsyncCallbackJsonWebHandler("/manual", [](AsyncWebServerRequest *request, JsonVariant &json) {
  if(!json.is<JsonObject>()) {
    sendErrorResponse(request, 400, "Received data is not a JSON object");
    return;
  }
  
  JsonObject jsonObj = json.as<JsonObject>();
  serializeJsonPretty(jsonObj, Serial); // Debug output

  // Extract and validate required fields
  if(!jsonObj.containsKey("fan_volt") || !jsonObj.containsKey("heater")) {
    sendErrorResponse(request, 400, "Missing required fields");
    return;
  }
  
  // Unpack the JSON fields
  float fanVolt = jsonObj["fan_volt"];
  bool heater = jsonObj["heater"];
  
  // Validate fan voltage (0-10V)
  if(fanVolt < 0.0f || fanVolt > 10.0f) {
    sendErrorResponse(request, 400, "fan_volt must be between 0 and 10");
    return;
  }
  
  // Set target state to MANUAL
  SystemState targetState = SystemState::MANUAL;
  unsigned long durationMs = 0; // Indefinite

  if (enqueueState(targetState, durationMs, fanVolt, heater)) {
    sendOkResponse(request, targetState == SystemState::MANUAL ? "MANUAL" : "UNKNOWN");
  } else {
    sendErrorResponse(request, 500, "Failed to enqueue state");
  }
});

void stateQueueHandler(State state) {
  SystemState previousState;
  
  if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdTRUE){
    previousState = currentState;
    currentState = state.state;
    stateStartTime = millis();

    if (state.duration > 0)
    {
      stateEndTime = stateStartTime + state.duration;
    }
    else
    {
      stateEndTime = 0; // infinite duration
    }
    xSemaphoreGive(stateMutex);
  }

  Serial.print("State transition: ");
  Serial.print(getStateName(previousState));
  Serial.print(" -> ");
  Serial.println(getStateName(state.state));

  // Set fan voltage
  commandFanVoltage(state.fanVoltage);

  // Set heater relay
  if (state.heaterOn) {
    relayOn(PIN_HEATER_RELAY);
  } else {
    relayOff(PIN_HEATER_RELAY);
  }
}

//------------------------------------------------
// ROUTES
//------------------------------------------------
void setupRoutes() {
  // TODO Add emergency shutdown route
  // TODO Add status route ?
}

//------------------------------------------------
// FREERTOS QUEUE SETUP
//------------------------------------------------

// State worker task
void stateWorker(void* pv){
  State state;
  while(true){
    if(xQueueReceive(stateQueue, &state, portMAX_DELAY) == pdTRUE){
      stateQueueHandler(state);
    } 
  }
}

// Setup state queue and worker task
void setupStateQueue() {
  stateQueue = xQueueCreate(10, sizeof(State));
  if(stateQueue == NULL) {
    Serial.println("Failed to create state queue");
    updateLCD(0.0f, 0.0f); // TODO Indicate error on LCD
    while(true) {
      // Softlock until reset
      delay(1000);
    }
  }

  // Create the state worker task
  vTaskDelay(pdMS_TO_TICKS(100));
  xTaskCreatePinnedToCore(
    stateWorker,
    "StateWorker",
    4096,
    NULL,
    1,
    NULL,
    1
  );
}

//--------------------------------------------------
// DEBUG FUNCTIONS
//--------------------------------------------------

// Handle serial commands for debugging set fan percent or voltage
void handleDebugSerialCommand() {
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd.startsWith("s=")) {
    float inputPct = cmd.substring(2).toFloat();
    inputPct = constrain(inputPct, 0.0f, 100.0f);

    float expectedVoltage = interpolateVoltage(inputPct);
    float correctedPercent = interpolatePercentForVoltage(expectedVoltage);

    currentPercent = correctedPercent;

    uint32_t duty = percentToDuty(correctedPercent);
    ledcWrite(LEDC_CHANNEL, duty);

    Serial.printf("Cmd=%.1f%% | Target V=%.2f | CalPWM=%.2f%% | duty=%u\n",
                  inputPct, expectedVoltage, correctedPercent, duty);

    updateLCD(inputPct, expectedVoltage);
  }
  else if (cmd.startsWith("v=")) {
    float volts = cmd.substring(2).toFloat();
    volts = constrain(volts, 0.0f, 10.0f); // within measured range
    commandedVoltage = volts;

    float pwmPercent = interpolatePercentForVoltage(volts);
    appliedPWMpercent = pwmPercent;

    uint32_t duty = percentToDuty(pwmPercent);
    ledcWrite(LEDC_CHANNEL, duty);

    Serial.printf("CmdV=%.2f V  -> PWM=%.2f%% (duty=%u)\n",
                  volts, pwmPercent, duty);

    updateLCD(volts, pwmPercent);
  }
  else {
    Serial.println("Unknown cmd. Use s=<0-100> to set percent.");
  }
}

//--------------------------------------------------
// WIFI SETUP
//--------------------------------------------------

bool connectWiFi() {
  Serial.print("Configuring static IP... ");
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS)) {
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

    server.addHandler(manageAutoHandler);
    server.addHandler(manageManualHandler);
    setupRoutes();
    server.begin();

    return true;
  } else {
    Serial.println("WiFi connect timeout.");
    return false;
  }
}

//------------------------------------------------
// SETUP
//------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);

  // Heater relay pin setup
  pinMode(PIN_HEATER_RELAY, OUTPUT);
  relayOff(PIN_HEATER_RELAY); // Start with heater off

  // PWM setup
  ledcSetup(LEDC_CHANNEL, PWM_FREQ_HZ, PWM_RES_BITS);
  ledcAttachPin(PWM_OUT_PIN, LEDC_CHANNEL);
  ledcWrite(LEDC_CHANNEL, 0);

  // LCD setup
  setupLCD();

  // Create mutex for state access
  stateMutex = xSemaphoreCreateMutex();
  if(stateMutex == NULL) {
    Serial.println("Failed to create state mutex");
    updateLCD(0.0f, 0.0f); // TODO Indicate error on LCD
    while(true) {
      // Softlock until reset
      delay(1000);
    }
  }

  // Setup FreeRTOS state queue and worker task
  setupStateQueue();

  // Connect to WiFi
  if (!connectWiFi()) {
    Serial.println("Failed to connect to WiFi. Require restart...");
    updateLCD(0.0f, 0.0f); // TODO Indicate error on LCD
    while(true) {
      // Softlock until reset
      delay(1000);
    }
  }
}


//------------------------------------------------
// MAIN LOOP
//------------------------------------------------
void loop() {
  unsigned long currentTime = millis();

  // Lock mutex before reading shared variables
  if(xSemaphoreTake(stateMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
    SystemState localState = currentState;
    unsigned long localEndTime = stateEndTime;
    xSemaphoreGive(stateMutex);
    
    if(localState != SystemState::MANUAL) {
      if(localEndTime > 0 && currentTime >= localEndTime) {
        emergencyShutdown();
      }
    }
  }
  
  if(IS_DEBUG_SERIAL_COMMAND) {
    if (Serial.available()) {
      handleDebugSerialCommand();
    }
  }
  
  delay(100);
}