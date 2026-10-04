# Hardware Notes

The original university prototype used:

* ESP32
* YF-S201 water-flow sensor
* LD2410C presence sensor
* FC-37 water-contact sensor
* OLED display
* LEDs
* buzzer

## Original Demo Setup

The LD2410C was configured for short-range classroom testing around the monitored sink area.

The software uses these main sensor values:

```text
water_flow
human_present
water_detected
running_duration_sec
flow_rate_lpm
```

The same general data structure is also used by the software simulator.

## Current Demo

The physical prototype is not required for the current repository demo.

The project can currently be tested using:

* the React dashboard simulation controls
* the Python MQTT simulator
* the FastAPI backend
* MongoDB
* WebSocket updates

The original hardware is no longer available in my current development environment.

## Hardware Evidence

Useful evidence from the original project can include:

* prototype photos
* wiring photos
* serial monitor output
* MQTT messages
* dashboard screenshots
* Telegram alert screenshots

## Limitations

* flow readings need calibration
* presence detection depends on sensor position
* the hardware was tested in a controlled classroom setup
* thresholds would need to be adjusted for a real installation
* the prototype is not a certified safety system
