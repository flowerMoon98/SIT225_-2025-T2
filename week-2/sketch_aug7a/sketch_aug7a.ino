#include <DHT.h>

#define DHTPIN 2        // Data pin connected to D2
#define DHTTYPE DHT22   // DHT 22 (AM2302)

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  while (!Serial); // Wait for Serial Monitor
  dht.begin();
}

void loop() {
  delay(10000); // Sample every 10 seconds

  float temp = dht.readTemperature();
  float humid = dht.readHumidity();

  if (!isnan(temp) && !isnan(humid)) {
    Serial.print(temp);     // Temperature first
    Serial.print(",");
    Serial.println(humid);  // Humidity second
  } else {
    Serial.println("NaN,NaN");
  }
}
