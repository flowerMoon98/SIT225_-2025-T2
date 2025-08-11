#include "arduino_secrets.h"     // include secrets FIRST
#include "thingProperties.h"
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  delay(1500);

  initProperties();                          // uses SECRET_SSID/PASS
  dht.begin();

  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  ArduinoCloud.update();

  static unsigned long last = 0;
  const unsigned long interval = 5000;       // ≥2s for DHT22; 5s is safe
  if (millis() - last >= interval) {
    last = millis();

    float t = dht.readTemperature();         // °C
    float h = dht.readHumidity();            // %
    if (!isnan(t) && !isnan(h)) {
      // publish to Cloud variables (must exist in your Thing)
      temperature = t;
      humidity    = h;

      Serial.print("DHT -> T: "); Serial.print(t);
      Serial.print(" °C  H: ");   Serial.println(h);
    } else {
      Serial.println("DHT read failed");
    }
  }
}

// Only required if vars are READ_WRITE; harmless to keep
void onTemperatureChange() {}
void onHumidityChange() {}