#include <Arduino_LSM6DS3.h>

const unsigned long SAMPLE_PERIOD_MS = 20; // 50 Hz
unsigned long lastMs = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }        // wait for USB
  if (!IMU.begin()) {
    Serial.println("ERR: IMU init failed");
    while (1) { delay(1000); }
  }
  Serial.println("gx,gy,gz");  // header (Python will skip this)
}

void loop() {
  unsigned long now = millis();
  if (now - lastMs >= SAMPLE_PERIOD_MS) {
    lastMs = now;
    float gx, gy, gz;
    if (IMU.gyroscopeAvailable()) {
      IMU.readGyroscope(gx, gy, gz); // deg/s
      Serial.print(gx, 3); Serial.print(',');
      Serial.print(gy, 3); Serial.print(',');
      Serial.println(gz, 3);
    }
  }
}