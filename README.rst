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
    
    
Callback
--------
We use pydispatcher for callback

.. code-block:: python

   from pydispatch import dispatcher
   
   def my_callback(sender, signal, **kwargs):
      print(sender)  # zigate instance
      print(signal)  # one of EVENT
	   print(kwargs)  # contains device and/or attribute changes, etc
     
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



MQTT Broker
-----------


python3 -m zigate.mqtt_broker --device auto --mqtt_host localhost:1883

the broker publish the following topics:
zigate/device_changed/[addr]
Payload example :

.. code-block:: python

   'zigate/device_changed/522a'
   {"addr": "522a", "endpoints": [{"device": 0, "clusters": [{"cluster": 1026, "attributes": [{"value": 22.27, "data": 2227, "unit": "\u00b0C", "name": "temperature", "attribute": 0}]}, {"cluster": 1027, "attributes": [{"value": 977, "data": 977, "unit": "mb", "name": "pressure", "attribute": 0}, {"value": 977.7, "data": 9777, "unit": "mb", "name": "pressure2", "attribute": 16}, {"data": -1, "attribute": 20}]}, {"cluster": 1029, "attributes": [{"value": 35.03, "data": 3503, "unit": "%", "name": "humidity", "attribute": 0}]}], "profile": 0, "out_clusters": [], "in_clusters": [], "endpoint": 1}], "info": {"power_source": 0, "ieee": "158d0002271c25", "addr": "522a", "id": 2, "rssi": 255, "last_seen": "2018-02-21 09:41:27"}}

zigate/device_removed 
Payload example :

.. code-block:: python

   {"addr": "522a"}
   
zigate/attribute_changed/[addr]/[endpoint]/[cluster]/[attribute]
payload is changed attribute
Payload example :

.. code-block:: python

   'zigate/attribute_changed/522a/01/0403/0010'
   {"cluster": 1027, "value": 978.5, "data": 9785, "attribute": 16, "unit": "mb", "endpoint": 1, "addr": "522a", "name": "pressure2"}

you can send command to zigate using the topic zigate/command
payload should be :

.. code-block:: python

   {"function": "function_name", "args": ["optional","args","list"]}

   # example to start permit join
   payload = '{"function": "permit_join"}'
   client.publish('zigate/command', payload)
   
The broker will publish the result using the topic "zigate/command/result"
Payload example :

.. code-block:: python

   {"function": "permit_join", "result": 0}

All the zigate functions can be call

.. code-block:: python

   # turn on endpoint 1
   payload = '{"function": "action_onoff", "args": ["522a", 1, 1]}'
   client.publish('zigate/command', payload)
   
   # turn off endpoint 1
   payload = '{"function": "action_onoff", "args": ["522a", 1, 0]}'
   client.publish('zigate/command', payload)
   
   
   