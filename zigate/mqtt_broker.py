'''
Created on 21 févr. 2018

@author: sramage
'''

from pydispatch import dispatcher
import logging
from zigate.const import *
from zigate.core import DeviceEncoder
import paho.mqtt.client as mqtt
import json


class MQTT_Broker(object):
    def __init__(self, zigate, mqtt_host='localhost:1883', username=None, password=None):
        self._mqtt_host = mqtt_host
        self.zigate = zigate
        self.client = mqtt.Client()
        if username is not None:
            self.client.username_pw_set(username, password)
        dispatcher.connect(self.attribute_changed, ZIGATE_ATTRIBUTE_ADDED)
        dispatcher.connect(self.attribute_changed, ZIGATE_ATTRIBUTE_UPDATED)
        dispatcher.connect(self.device_changed, ZIGATE_DEVICE_ADDED)
        dispatcher.connect(self.device_changed, ZIGATE_DEVICE_UPDATED)
        dispatcher.connect(self.device_removed, ZIGATE_DEVICE_REMOVED)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def connect(self):
        host, port = self._mqtt_host.split(':')
        port = int(port)
        self.client.connect(host, port)
        
    def start(self):
        self.connect()
        self.zigate.autoStart()
        self.zigate.start_auto_save()
        self.client.loop_forever()

    def _publish(self, topic, payload=None):
        if payload:
            payload = json.dumps(payload, cls=DeviceEncoder)
        logging.info('Publish {}'.format(topic))
        self.client.publish(topic, payload, retain=True)

    def device_changed(self, device):
        logging.debug('device_changed {}'.format(device))
        self._publish('zigate/device_changed/{}'.format(device.addr), device)

    def device_removed(self, addr):
        logging.debug('device_removed {}'.format(addr))
        self._publish('zigate/device_removed', addr)

    def attribute_changed(self, attribute):
        logging.debug('attribute_changed {}'.format(attribute))
        self._publish('zigate/attribute_changed/{0[addr]}/'
                      '{0[endpoint]:02x}/{0[cluster]:04x}/'
                      '{0[attribute]:04x}'.format(attribute), attribute)

    def on_connect(self, client, userdata, flags, rc):
        logging.info("MQTT connected with result code {}".format(rc))
        client.subscribe("zigate/command/#")

    def on_message(self, client, userdata, msg):
        payload = {}
        if msg.payload:
            payload = json.loads(msg.payload.decode())
        if msg.topic == 'zigate/command':
            func_name = payload.get('function')
            args = payload.get('args', [])
            if hasattr(self.zigate, func_name):
                func = getattr(self.zigate, func_name)
                if callable(func):
                    try:
                        result = func(*args)
                    except:
                        result = None
                        logging.error('Error calling function {}'.format(func_name))
                else:
                    result = func
                if result:
                    self._publish('zigate/command/result', {'function': func_name,
                                                            'result': result
                                                            })
            else:
                logging.error('ZiGate has no function named {}'.format(func_name))


if __name__ == '__main__':
    logging.basicConfig()
    logging.root.setLevel(logging.INFO)
    import argparse
    from zigate import ZiGate, ZiGateWiFi

    parser = argparse.ArgumentParser()
    parser.add_argument('--device', help='ZiGate usb port or host:port', default='auto')
    parser.add_argument('--mqtt_host', help='MQTT host:port', default='localhost:1883')
    parser.add_argument('--mqtt_username', help='MQTT username', default=None)
    parser.add_argument('--mqtt_password', help='MQTT password', default=None)
    args = parser.parse_args()

    if ':' in args.device:  # supposed IP:PORT
        host, port = args.device.split(':')
        z = ZiGateWiFi(host, port, auto_start=False)
    else:
        z = ZiGate(args.device, auto_start=False)
    broker = MQTT_Broker(z, args.mqtt_host, args.mqtt_username, args.mqtt_password)
    broker.start()
