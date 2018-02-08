======
zigate
======

python library for zigate http://zigate.fr/
This library manage communication between python and zigate key, both USB and WiFi key are supported (wifi is almost untested)
ZiGate is an universal gateway compatible with a lot of ZigBee device (like Xiaomi, Philipps Hue, Ikea, etc)


Getting Started
===============

Installation
------------
To install simply do::

    pip3 install zigate


Usage
-----

.. code-block:: python

   # if you want logging
   import logging
   logging.basicConfig()
   logging.root.setLevel(logging.DEBUG)

   import zigate
   z = zigate.ZiGate(port=None) # Leave None to auto-discover the port

   print(z.get_version())
   OrderedDict([('major', 1), ('installer', '30b'), ('rssi', 0), ('version', '3.0b')])

   print(z.get_version_text())
   3.0b

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
   {1: {'0405_0000': {'endpoint': 1,
      'data': 3997,
      'cluster': 1029,
      'attribute': 0,
      'status': 0,
      'friendly_name': 'humidity',
      'value': 39.97,
      'unit': '%'},
     '0000_0005': {'endpoint': 1,
      'data': '6c756d692e77656174686572',
      'cluster': 0,
      'attribute': 5,
      'status': 0,
      'friendly_name': 'type',
      'value': 'lumi.weather',
      'unit': ''},
     '0000_0001': {'cluster': 0,
      'endpoint': 1,
      'status': 0,
      'attribute': 1,
      'data': 3},
     '0403_0000': {'endpoint': 1,
      'data': 976,
      'cluster': 1027,
      'attribute': 0,
      'status': 0,
      'friendly_name': 'pressure',
      'value': 976,
      'unit': 'mb'},
     '0000_ff01': {'cluster': 0,
      'endpoint': 1,
      'status': 0,
      'attribute': 65281,
      'data': '0121ef0b0421a81305210800062401000000006429a6096521a30f662b737d01000a210000'},
     '0403_0010': {'endpoint': 1,
      'data': 9762,
      'cluster': 1027,
      'attribute': 16,
      'status': 0,
      'friendly_name': 'detailled pressure',
      'value': 976.2,
      'unit': 'mb'},
     '0403_0014': {'cluster': 1027,
      'endpoint': 1,
      'status': 0,
      'attribute': 20,
      'data': -1},
     '0402_0000': {'endpoint': 1,
      'data': 2447,
      'cluster': 1026,
      'attribute': 0,
      'status': 0,
      'friendly_name': 'temperature',
      'value': 24.47,
      'unit': '°C'}}}
   
   
   # get well known attributes
   >>> for attribute in z.devices[0].properties:
       	print(attribute)
   {'endpoint': 1, 'data': 3997, 'cluster': 1029, 'attribute': 0, 'status': 0, 'friendly_name': 'humidity', 'value': 39.97, 'unit': '%'}
   {'endpoint': 1, 'data': '6c756d692e77656174686572', 'cluster': 0, 'attribute': 5, 'status': 0, 'friendly_name': 'type', 'value': 'lumi.weather', 'unit': ''}
   {'endpoint': 1, 'data': 976, 'cluster': 1027, 'attribute': 0, 'status': 0, 'friendly_name': 'pressure', 'value': 976, 'unit': 'mb'}
   {'endpoint': 1, 'data': 9762, 'cluster': 1027, 'attribute': 16, 'status': 0, 'friendly_name': 'detailled pressure', 'value': 976.2, 'unit': 'mb'}
   {'endpoint': 1, 'data': 2447, 'cluster': 1026, 'attribute': 0, 'status': 0, 'friendly_name': 'temperature', 'value': 24.47, 'unit': '°C'}
   
   # get specific property
   >>> z.devices[0].get_property('temperature')
   {'endpoint': 1,
    'data': 2447,
    'cluster': 1026,
    'attribute': 0,
    'status': 0,
    'friendly_name': 'temperature',
    'value': 24.47,
    'unit': '°C'}

Callback
--------
We use pydispatch to catch some events

.. code-block:: python

   from pydispatch import dispatcher
   
   def my_callback(**kwargs):
	    print(kwargs)
     
   dispatcher.connect(my_callback, zigate.ZIGATE_ATTRIBUTE_UPDATED)

   z = zigate.ZiGate()
   
   # to catch any events
   dispatcher.connect(my_callback, dispatcher.Any)
      

event can be :

.. code-block:: python

   zigate.ZIGATE_DEVICE_ADDED
   zigate.ZIGATE_DEVICE_UPDATED
   zigate.ZIGATE_DEVICE_REMOVED
   zigate.ZIGATE_ATTRIBUTE_ADDED
   zigate.ZIGATE_ATTRIBUTE_UPDATED

kwargs depends of the event type
for zigate.ZIGATE_DEVICE_ADDED:
kwargs contains device

for zigate.ZIGATE_DEVICE_UPDATED
kwargs contains device

for zigate.ZIGATE_DEVICE_REMOVED
kwargs contains addr (the device short address)

for zigate.ZIGATE_ATTRIBUTE_ADDED:
kwargs contains device and discovered attribute 

for zigate.ZIGATE_ATTRIBUTE_UPDATED
kwargs contains device and updated attribute



Wifi ZiGate
-----------

WiFi ZiGate is also supported :

.. code-block:: python

   import zigate
   z = zigate.ZiGateWiFi(host='192.168.0.10', port=9999)





