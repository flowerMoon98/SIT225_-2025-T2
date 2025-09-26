#include <DHT.h>
#include <Arduino_LSM6DS3.h>

// ---------- Pins ----------
#define DHTPIN   2
#define DHTTYPE  DHT22
#define PIR_PIN  3
#define LED_PIN  LED_BUILTIN

// ---------- Modes ----------
#define OUTPUT_CSV   1   // 0 = JSON, 1 = CSV

// ---------- PIR settings ----------
#define PIR_ACTIVE_HIGH 1
const unsigned long OCCUPIED_LATCH_MS = 3000;

// ---------- Timings ----------
const unsigned long DHT_PERIOD    = 2000;
const unsigned long PIR_PERIOD    = 50;
const unsigned long IMU_PERIOD    = 50;    // 20 Hz
const unsigned long REPORT_PERIOD = 250;   // ~4x/s

// ---------- Focus thresholds (tune) ----------
float HI_FOCUSED_MAX        = 28.0f;   // comfy if HI <= 28 °C
float THRESH_FIDGET_FOCUSED = 0.015f;  // set ~2–3x your idle baseline

// ---------- State ----------
DHT dht(DHTPIN, DHTTYPE);
unsigned long tDht=0, tPir=0, tImu=0, tRpt=0, lastMotionMs=0;
float tempC=NAN, humPct=NAN, heatIdxC=NAN;
bool  occupied=false, focused=false;

// IMU / fidget
bool  imuOk=false, havePrevAccel=false;
float ax=0, ay=0, az=0;
float fidget=0.0f;
const float FIDGET_DECAY = 0.95f;   // 0.90 = more responsive; 0.98 = very smooth

// Heat index (°C). Below ~26 °C, just return air temp.
float heatIndexC(float T, float R) {
  if (T < 26.0f) return T;
  float Tf = T*1.8f + 32.0f;
  float HI = -42.379 + 2.04901523*Tf + 10.14333127*R
           - 0.22475541*Tf*R - 0.00683783*Tf*Tf - 0.05481717*R*R
           + 0.00122874*Tf*Tf*R + 0.00085282*Tf*R*R - 0.00000199*Tf*Tf*R*R;
  return (HI - 32.0f)/1.8f;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  pinMode(LED_PIN, OUTPUT);

  // DHT on internal pull-up if no 10k
  pinMode(DHTPIN, INPUT_PULLUP);
  dht.begin();

#if PIR_ACTIVE_HIGH
  pinMode(PIR_PIN, INPUT);         // HIGH = motion
#else
  pinMode(PIR_PIN, INPUT_PULLUP);  // LOW  = motion
#endif

  imuOk = IMU.begin();
#if OUTPUT_CSV
  Serial.println("ms,temp_c,hum_pct,heat_index_c,pir_raw,motion,occupied,fidget,focused");
#else
  Serial.println("DHT22 + PIR + IMU running (JSON)...");
#endif
}

void loop() {
  unsigned long now = millis();

  // ---- PIR ----
  static bool motionNow=false;
  if (now - tPir >= PIR_PERIOD) {
    tPir = now;
    int pirRaw = digitalRead(PIR_PIN);
    motionNow = PIR_ACTIVE_HIGH ? (pirRaw == HIGH) : (pirRaw == LOW);
    if (motionNow) lastMotionMs = now;
    occupied = (now - lastMotionMs) < OCCUPIED_LATCH_MS;
    digitalWrite(LED_PIN, motionNow ? HIGH : LOW);
  }

  // ---- DHT ----
  if (now - tDht >= DHT_PERIOD) {
    tDht = now;
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (!isnan(h) && !isnan(t)) {
      humPct = h;
      tempC  = t;
      heatIdxC = heatIndexC(t, h);
    }
  }

  // ---- IMU / fidget ----
  if (imuOk && (now - tImu >= IMU_PERIOD)) {
    tImu = now;
    float x,y,z;
    if (IMU.accelerationAvailable()) {
      IMU.readAcceleration(x, y, z); // g
      if (havePrevAccel) {
        float delta = fabs(x-ax) + fabs(y-ay) + fabs(z-az);
        fidget = FIDGET_DECAY * fidget + (1.0f - FIDGET_DECAY) * delta;
      } else {
        havePrevAccel = true;
      }
      ax=x; ay=y; az=z;
    }
  }

  // ---- Focus flag ----
  focused = occupied &&
            ( !isnan(heatIdxC) ? (heatIdxC <= HI_FOCUSED_MAX) : true ) &&
            ( fidget < THRESH_FIDGET_FOCUSED );

  // ---- Report ----
  if (now - tRpt >= REPORT_PERIOD) {
    tRpt = now;
    int pirRaw = digitalRead(PIR_PIN);
#if OUTPUT_CSV
    Serial.print(now); Serial.print(',');
    Serial.print(isnan(tempC)?-999.0:tempC, 2); Serial.print(',');
    Serial.print(isnan(humPct)?-999.0:humPct, 1); Serial.print(',');
    Serial.print(isnan(heatIdxC)?-999.0:heatIdxC, 2); Serial.print(',');
    Serial.print(pirRaw); Serial.print(',');
    Serial.print((int)(PIR_ACTIVE_HIGH ? (pirRaw==HIGH) : (pirRaw==LOW))); Serial.print(',');
    Serial.print((int)occupied); Serial.print(',');
    Serial.print(fidget, 4); Serial.print(',');
    Serial.println((int)focused);
#else
    bool motionNowPrint = PIR_ACTIVE_HIGH ? (pirRaw == HIGH) : (pirRaw == LOW);
    Serial.print("{\"ms\":"); Serial.print(now);
    Serial.print(",\"temp_c\":"); Serial.print(isnan(tempC)?-999.0:tempC, 2);
    Serial.print(",\"hum_pct\":"); Serial.print(isnan(humPct)?-999.0:humPct, 1);
    Serial.print(",\"heat_index_c\":"); Serial.print(isnan(heatIdxC)?-999.0:heatIdxC, 2);
    Serial.print(",\"pir_raw\":"); Serial.print(pirRaw);
    Serial.print(",\"motion\":"); Serial.print(motionNowPrint ? 1 : 0);
    Serial.print(",\"occupied\":"); Serial.print(occupied ? 1 : 0);
    Serial.print(",\"fidget\":"); Serial.print(fidget, 4);
    Serial.print(",\"focused\":"); Serial.print(focused ? 1 : 0);
    Serial.println("}");
#endif
  }
}
