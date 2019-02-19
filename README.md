# zigate

[![Build Status](https://travis-ci.org/doudz/zigate.svg?branch=master)](https://travis-ci.org/doudz/zigate)
[![PyPI version](https://badge.fury.io/py/zigate.svg)](https://pypi.python.org/pypi/zigate)
[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/doudz/zigate.svg)](http://isitmaintained.com/project/doudz/zigate "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/doudz/zigate.svg)](http://isitmaintained.com/project/doudz/zigate "Percentage of issues still open")
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/sebramage)

Python library for [ZiGate](http://zigate.fr/).
This library manage communication between python and zigate key, both USB and WiFi key are supported.

ZiGate is an universal gateway compatible with a lot of ZigBee device (like Xiaomi, Philipps Hue, Ikea, etc).

Current coverage :

* Commands 69 / 91
* Responses 48 / 52

## Getting Started

### Installation

To install simply do:

```bash
pip3 install zigate
```

Or if you've planned to use mqtt

```bash
pip3 install zigate[mqtt]
```

### Usage

```python
# if you want logging
import logging
logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

import zigate
z = zigate.connect(port=None) # Leave None to auto-discover the port

print(z.get_version())
OrderedDict([('major', 1), ('installer', '30c'), ('rssi', 0), ('version', '3.0c')])

print(z.get_version_text())
3.0c

# refresh devices list
z.get_devices_list()

# start inclusion mode
>>> z.permit_join()
>>> z.is_permitting_join()
True

# list devices
>>> z.devices
[Device 677c , Device b8ce , Device 92a7 , Device 59ef ]
>>> z.devices[0].addr
'677c'

# get all discovered endpoints
>>> z.devices[0].endpoints
{1: {
  'clusters': {0: Cluster 0 General: Basic,
   1026: Cluster 1026 Measurement: Temperature,
   1027: Cluster 1027 Measurement: Atmospheric Pressure,
   1029: Cluster 1029 Measurement: Humidity},
  }}


# get well known attributes
>>> for attribute in z.devices[0].properties:
     print(attribute)
{'data': 'lumi.weather', 'name': 'type', 'attribute': 5, 'value': 'lumi.weather'}
{'data': '0121c70b0421a8010521090006240100000000642932096521851c662bd87c01000a210000', 'name': 'battery', 'value': 3.015, 'unit': 'V', 'attribute': 65281}
{'data': -1983, 'name': 'temperature', 'value': -19.83, 'unit': '°C', 'attribute': 0}
{'data': 9779, 'name': 'pressure2', 'value': 977.9, 'unit': 'mb', 'attribute': 16}
{'data': 977, 'name': 'pressure', 'value': 977, 'unit': 'mb', 'attribute': 0}
{'data': 4484, 'name': 'humidity', 'value': 44.84, 'unit': '%', 'attribute': 0}

# get specific property
>>> z.devices[0].get_property('temperature')
{'data': -1983,
 'name': 'temperature',
 'value': -19.83,
 'unit': '°C',
 'attribute': 0}

 # call action on devices
 z.action_onoff('b8ce', 1, zigate.ON)

 # or from devices
 z.devices[1].action_onoff(zigate.ON)

 # OTA process
 # Load image and send headers to ZiGate
 z.ota_load_image('path/to/ota/image_file.ota')
 # Tell client that image is available
 z.ota_image_notify('addr')
 # It will take client usually couple seconds to query headers
 # from server. Upgrade process start automatically if correct
 # headers are loaded to ZiGate. If you have logging level debug
 # enabled you will get automatically progress updates.
 # Manually check ota status - logging level INFO
 z.get_ota_status()
 # Whole upgrade process time depends on device and ota image size
 # Upgrading ikea bulb took ~15 minutes
 # Upgrading ikea remote took ~45 minutes

```

### OTA Update

Some devices (like Ikea Tradfri) could be updated.
For Ikea, you could download available OTA files using the following command :

`python3 zigate.ikea_ota_download`

```python
 # OTA process
 # Load image and send headers to ZiGate
 z.ota_load_image('path/to/ota/image_file.ota')
 # Tell client that image is available
 z.ota_image_notify('addr')
 # It will take client usually couple seconds to query headers
 # from server. Upgrade process start automatically if correct
 # headers are loaded to ZiGate. If you have logging level debug
 # enabled you will get automatically progress updates.
 # Manually check ota status - logging level INFO
 z.get_ota_status()
 # Whole upgrade process time depends on device and ota image size
 # Upgrading ikea bulb took ~15 minutes
 # Upgrading ikea remote took ~45 minutes

```

### Callback

We use pydispatcher for callback

```python
from zigate import dispatcher

def my_callback(sender, signal, **kwargs):
    print(sender)  # zigate instance
    print(signal)  # one of EVENT
    print(kwargs)  # contains device and/or attribute changes, etc

dispatcher.connect(my_callback, zigate.ZIGATE_ATTRIBUTE_UPDATED)

z = zigate.connect()

# to catch any events
dispatcher.connect(my_callback, dispatcher.Any)
```

event can be :

```python
zigate.ZIGATE_DEVICE_ADDED
zigate.ZIGATE_DEVICE_UPDATED
zigate.ZIGATE_DEVICE_REMOVED
zigate.ZIGATE_DEVICE_ADDRESS_CHANGED
zigate.ZIGATE_ATTRIBUTE_ADDED
zigate.ZIGATE_ATTRIBUTE_UPDATED
zigate.ZIGATE_DEVICE_NEED_DISCOVERY
```

kwargs depends of the event type:

* for `zigate.ZIGATE_DEVICE_ADDED` kwargs contains device.
* for `zigate.ZIGATE_DEVICE_UPDATED` kwargs contains device.
* for `zigate.ZIGATE_DEVICE_REMOVED` kwargs contains addr (the device short address).
* for `zigate.ZIGATE_DEVICE_ADDRESS_CHANGED` kwargs contains old_addr and new_addr (used when re-pairing an already known device).
* for `zigate.ZIGATE_ATTRIBUTE_ADDED` kwargs contains device and discovered attribute.
* for `zigate.ZIGATE_ATTRIBUTE_UPDATED` kwargs contains device and updated attribute.
* for `zigate.ZIGATE_DEVICE_NEED_DISCOVERY` kwargs contains device.

## Wifi ZiGate

WiFi ZiGate is also supported:

```python
import zigate
z = zigate.connect(host='192.168.0.10')

# or if you want to set the port
z = zigate.connect(host='192.168.0.10:1234')
```

## MQTT Broker

This requires paho-mqtt. It could be install as a dependency with `pip3 install zigate[mqtt]`

```bash
python3 -m zigate.mqtt_broker --device auto --mqtt_host localhost:1883
```

Add `--mqtt_username` and `--mqtt_password` as arguments and allow them to be used to establish connection to the MQTT broker.

The broker publish the following topics: zigate/device_changed/[addr]

Payload example :

```python
'zigate/device_changed/522a'
{"addr": "522a", "endpoints": [{"device": 0, "clusters": [{"cluster": 1026, "attributes": [{"value": 22.27, "data": 2227, "unit": "\u00b0C", "name": "temperature", "attribute": 0}]}, {"cluster": 1027, "attributes": [{"value": 977, "data": 977, "unit": "mb", "name": "pressure", "attribute": 0}, {"value": 977.7, "data": 9777, "unit": "mb", "name": "pressure2", "attribute": 16}, {"data": -1, "attribute": 20}]}, {"cluster": 1029, "attributes": [{"value": 35.03, "data": 3503, "unit": "%", "name": "humidity", "attribute": 0}]}], "profile": 0, "out_clusters": [], "in_clusters": [], "endpoint": 1}], "info": {"power_source": 0, "ieee": "158d0002271c25", "addr": "522a", "id": 2, "rssi": 255, "last_seen": "2018-02-21 09:41:27"}}
```

zigate/device_removed.
Payload example :

```python
{"addr": "522a"}
```

zigate/attribute_changed/[addr]/[endpoint]/[cluster]/[attribute] payload is changed attribute.
Payload example :

```python
'zigate/attribute_changed/522a/01/0403/0010'
{"cluster": 1027, "value": 978.5, "data": 9785, "attribute": 16, "unit": "mb", "endpoint": 1, "addr": "522a", "name": "pressure2"}
```

You can send command to zigate using the topic zigate/command payload should be:

```python
{"function": "function_name", "args": ["optional","args","list"]}

# example to start permit join
payload = '{"function": "permit_join"}'
client.publish('zigate/command', payload)
```

The broker will publish the result using the topic "zigate/command/result".
Payload example :

```python
{"function": "permit_join", "result": 0}
```

All the zigate functions can be call:

```python
# turn on endpoint 1
payload = '{"function": "action_onoff", "args": ["522a", 1, 1]}'
client.publish('zigate/command', payload)

# turn off endpoint 1
payload = '{"function": "action_onoff", "args": ["522a", 1, 0]}'
client.publish('zigate/command', payload)
```

## Flasher

Python tool to flash your Zigate (Jennic JN5168)

Thanks to Sander Hoentjen (tjikkun) we now have a flasher !
[Original repo](https://github.com/tjikkun/zigate-flasher)

### Flasher Usage

```bash
usage: python3 -m zigate.flasher [-h] -p {/dev/ttyUSB0} [-w WRITE] [-s SAVE] [-e] [--pdm-only]

optional arguments:
  -h, --help            show this help message and exit
  -p {/dev/ttyUSB0}, --serialport {/dev/ttyUSB0}
                        Serial port, e.g. /dev/ttyUSB0
  -w WRITE, --write WRITE
                        Firmware bin to flash onto the chip
  -s SAVE, --save SAVE  File to save the currently loaded firmware to
  -e, --erase           Erase EEPROM
  --pdm-only            Erase PDM only, use it with --erase

```




