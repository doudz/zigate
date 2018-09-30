# zigate

[![Build Status](https://travis-ci.org/doudz/zigate.svg?branch=master)](https://travis-ci.org/doudz/zigate)
[![PyPI version](https://badge.fury.io/py/zigate.svg)](https://pypi.python.org/pypi/zigate)
[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/doudz/zigate.svg)](http://isitmaintained.com/project/doudz/zigate "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/doudz/zigate.svg)](http://isitmaintained.com/project/doudz/zigate "Percentage of issues still open")


python library for zigate <http://zigate.fr/> This library manage
communication between python and zigate key, both USB and WiFi key are
supported (wifi is almost untested) ZiGate is an universal gateway
compatible with a lot of ZigBee device (like Xiaomi, Philipps Hue, Ikea,
etc)

## Getting Started

### Installation

To install simply do:

```bash
pip3 install zigate
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

 or from devices
 z.devices[1].action_onoff(zigate.ON)
```

### Callback

We use pydispatcher for callback

```python
from pydispatch import dispatcher

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
zigate.ZIGATE_D
```