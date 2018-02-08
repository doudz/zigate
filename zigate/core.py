#! /usr/bin/python3
from binascii import (hexlify, unhexlify)
from time import (sleep, strftime, time)
from collections import OrderedDict
import logging
import json
import os
from pydispatch import dispatcher
from .transport import (ThreadSerialConnection, ThreadSocketConnection)
from .responses import (RESPONSES, Response)
from .attributes import ATTRIBUTES
import functools
import struct
import threading

LOGGER = logging.getLogger('zigate')

CLUSTERS = {0x0000: 'General: Basic',
            0x0001: 'General: Power Config',
            0x0002: 'General: Temperature Config',
            0x0003: 'General: Identify',
            0x0004: 'General: Groups',
            0x0005: 'General: Scenes',
            0x0006: 'General: On/Off',
            0x0007: 'General: On/Off Config',
            0x0008: 'General: Level Control',
            0x0009: 'General: Alarms',
            0x000A: 'General: Time',
            0x000F: 'General: Binary Input Basic',
            0x0020: 'General: Poll Control',
            0x0019: 'General: OTA',
            0x0101: 'General: Door Lock',
            0x0201: 'HVAC: Thermostat',
            0x0202: 'HVAC: Fan Control',
            0x0300: 'Lighting: Color Control',
            0x0400: 'Measurement: Illuminance',
            0x0402: 'Measurement: Temperature',
            0x0403: 'Measurement: Atmospheric Pressure',
            0x0405: 'Measurement: Humidity',
            0x0406: 'Measurement: Occupancy Sensing',
            0x0500: 'Security & Safety: IAS Zone',
            0x0702: 'Smart Energy: Metering',
            0x0B05: 'Misc: Diagnostics',
            0x1000: 'ZLL: Commissioning',
            0xFF01: 'Xiaomi private',
            0xFF02: 'Xiaomi private',
            0x1234: 'Xiaomi private'
            }

ZGT_LOG_LEVELS = ['Emergency', 'Alert', 'Critical', 'Error',
                  'Warning', 'Notice', 'Information', 'Debug']

STATUS_CODES = {0: 'Success', 1: 'Invalid parameters',
                2: 'Unhandled command', 3: 'Command failed',
                4: 'Busy', 5: 'Stack already started'}

# event signal
ZIGATE_DEVICE_ADDED = 'ZIGATE_DEVICE_ADDED'
ZIGATE_DEVICE_UPDATED = 'ZIGATE_DEVICE_UPDATED'
ZIGATE_DEVICE_REMOVED = 'ZIGATE_DEVICE_REMOVED'
ZIGATE_ATTRIBUTE_ADDED = 'ZIGATE_ATTRIBUTE_ADDED'
ZIGATE_ATTRIBUTE_UPDATED = 'ZIGATE_ATTRIBUTE_UPDATED'

BATTERY = 0
AC_POWER = 1

TYPE_COORDINATOR = '00'
TYPE_ROUTER = '01'
TYPE_LEGACY_ROUTER = '02'

AUTO_SAVE = 5*60  # 5 minutes


class ZiGate(object):

    def __init__(self, port='auto', path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True):
        self._buffer = b''
        self._devices = {}
        self._path = path
        self._version = None
        self._port = port
        self._last_response = {}  # response to last command type
        self._last_status = {}  # status to last command type
        self._save_lock = threading.Lock()
        self._autosavetimer = None
        self._closing = False
        self.connection = None
        self.setup_connection()
        if auto_start:
            self.init()
            if auto_save:
                self.start_auto_save()

    def setup_connection(self):
        self.connection = ThreadSerialConnection(self, self._port)

    def close(self):
        self._closing = True
        if self._autosavetimer:
            self._autosavetimer.cancel()
        try:
            self.save_state()
            if self.connection:
                self.connection.close()
        except Exception as e:
            LOGGER.error('Exception during closing {}'.format(e))

    def save_state(self, path=None):
        self._save_lock.acquire()
        path = path or self._path
        self._path = os.path.expanduser(path)
        with open(self._path, 'w') as fp:
            json.dump(list(self._devices.values()), fp, cls=DeviceEncoder,
                      sort_keys=True, indent=4, separators=(',', ': '))
        self._save_lock.release()

    def load_state(self, path=None):
        LOGGER.debug('Try loading persistent file')
        path = path or self._path
        self._path = os.path.expanduser(path)
        if os.path.exists(self._path):
            try:
                with open(self._path) as fp:
                    devices = json.load(fp)
                for data in devices:
                    device = Device.from_json(data)
                    self._devices[device.addr] = device
                LOGGER.debug('Load success')
                return True
            except Exception as e:
                LOGGER.error('Failed to load persistent file {}'.format(self._path))
                LOGGER.error('{}'.format(e))
        LOGGER.debug('No file to load')
        return False

    def start_auto_save(self):
        LOGGER.debug('Auto saving {}'.format(self._path))
        self.save_state()
        self._autosavetimer = threading.Timer(AUTO_SAVE, self.start_auto_save)
        self._autosavetimer.setDaemon(True)
        self._autosavetimer.start()

    def __del__(self):
        self.close()

    def init(self):
        self.load_state()
#         erase = not self.load_state()
#         if erase:
#             self.erase_persistent()
        self.set_channel()
        self.set_type(TYPE_COORDINATOR)
        self.start_network()
        self.get_devices_list(True)

    def zigate_encode(self, data):
        encoded = bytearray()
        for b in data:
            if b < 0x10:
                encoded.extend([0x02, 0x10 ^ b])
            else:
                encoded.append(b)
        return encoded

    def zigate_decode(self, data):
        flip = False
        decoded = bytearray()
        for b in data:
            if flip:
                flip = False
                decoded.append(b ^ 0x10)
            elif b == 0x02:
                flip = True
            else:
                decoded.append(b)
        return decoded

    def checksum(self, *args):
        chcksum = 0
        for arg in args:
            if isinstance(arg, int):
                chcksum ^= arg
                continue
            for x in arg:
                chcksum ^= x
        return chcksum

    def send_to_transport(self, data):
        if not self.connection.is_connected():
            raise Exception('Not connected to zigate')
        self.connection.send(data)

    def read_data(self, data):
        '''
        Read ZiGate output and split messages
        '''
        self._buffer += data
        endpos = self._buffer.find(b'\x03')
        while endpos != -1:
            startpos = self._buffer.find(b'\x01')
            # stripping starting 0x01 & ending 0x03
            raw_message = self._buffer[startpos + 1:endpos]
            threading.Thread(target=self.decode_data,args=(raw_message,)).start()
#             self.decode_data(raw_message)
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    def send_data(self, cmd, data="", wait_response=None):
        '''
        send data through ZiGate
        '''
        self._last_status[cmd] = None
        if wait_response:
            self._clear_response(wait_response)
        if isinstance(cmd, int):
            byte_cmd = struct.pack('!H', cmd)
        elif isinstance(data, str):
            byte_cmd = bytes.fromhex(cmd)
        else:
            byte_cmd = cmd
        if isinstance(data, str):
            byte_data = bytes.fromhex(data)
        else:
            byte_data = data
        assert type(byte_cmd) == bytes
        assert type(byte_data) == bytes
        length = int(len(data)/2)
        byte_length = length.to_bytes(2, 'big')
        checksum = self.checksum(byte_cmd, byte_length, byte_data)

        msg = struct.pack('!HHB%ds' % length, cmd, length, checksum, byte_data)
        LOGGER.debug('Msg to send {}'.format(msg))

        enc_msg = self.zigate_encode(msg)
        enc_msg.insert(0, 0x01)
        enc_msg.append(0x03)
        encoded_output = bytes(enc_msg)
        LOGGER.debug('REQUEST : 0x{:04x} {}'.format(cmd, data))
        LOGGER.debug('Encoded Msg to send {}'.format(encoded_output))

        self.send_to_transport(encoded_output)
        status = self._wait_status(cmd)
        if wait_response:
            r = self._wait_response(wait_response)
            return r
        return status

    @staticmethod
    def decode_struct(strct, msg):
        output = OrderedDict()
        while strct:
            key, elt_type = strct.popitem(last=False)
            # uint_8, 16, 32, 64 ... or predefined byte length
            if type(elt_type) == int:
                length = int(elt_type / 8)
                output[key] = hexlify(msg[:length])
                msg = msg[length:]
            # int (1 ou 2 bytes)
            elif elt_type in ('int', 'int8', 'int16'):
                if elt_type == 'int16':
                    index = 2
                else:
                    index = 1
                output[key] = int(hexlify(msg[:index]), 16)
                msg = msg[index:]
            # bool (2 bytes)
            elif elt_type == 'bool':
                output[key] = bool(int(hexlify(msg[:1])))
                msg = msg[1:]
            # element gives length of next element in message
            # (which could be raw)
            elif elt_type in ('len8', 'len16'):
                if elt_type == 'len16':
                    index = 2
                else:
                    index = 1
                length = int(hexlify(msg[0:index]), 16)
                output[key] = length
                msg = msg[index:]
                # let's get the next element
                key, elt_type = strct.popitem(last=False)
                if elt_type == 'raw':
                    output[key] = msg[:length]
                    msg = msg[length:]
                else:
                    output[key] = hexlify(msg[:length])
                    msg = msg[length:]
            # element gives number of next elements
            # (which can be of a defined length)
            elif elt_type == 'count':
                count = int(hexlify(msg[:1]), 16)
                output[key] = count
                msg = msg[1:]
                # let's get the next element
                # (list of elements referenced by the count)
                key, elt_type = strct.popitem(last=False)
                output[key] = []
                length = int(elt_type / 8)
                for i in range(count):
                    output[key].append(hexlify(msg[:length]))
                    msg = msg[length:]
            # remaining of the message
            elif elt_type == 'end':
                output[key] = hexlify(msg)
            # remaining of the message as raw data
            elif elt_type == 'rawend':
                output[key] = msg

        return output

    def decode_data(self, raw_message):
        decoded = self.zigate_decode(raw_message[1:-1])
        msg_type, length, checksum, value, rssi = \
            struct.unpack('!HHB%dsB' % (len(decoded) - 6), decoded)
        if length != len(value)+1:  # add rssi length
            LOGGER.error('Bad length {} != {} : {}'.format(length,
                                                           len(value),
                                                           value))
            return
        computed_checksum = self.checksum(decoded[:4], rssi, value)
        if checksum != computed_checksum:
            LOGGER.error('Bad checksum {} != {}'.format(checksum,
                                                        computed_checksum))
            return
        response = RESPONSES.get(msg_type, Response)(value, rssi)
        if msg_type != response.msg:
            LOGGER.warning('Unknown response 0x{:04x}'.format(msg_type))
        LOGGER.debug(response)
        self.interpret_response(response)
        self._last_response[msg_type] = response

    def interpret_response(self, response):
        if response.msg == 0x8000:  # status
            if response['status'] != 0:
                LOGGER.error('Command 0x{:04x} failed {} : {}'.format(response['packet_type'],
                                                                 response.status_text(),
                                                                 response['error']))
            self._last_status[response['packet_type']] = response['status']
        elif response.msg == 0x8015:  # device list
            keys = set(self._devices.keys())
            known_addr = set([d['addr'] for d in response['devices']])
            to_delete = keys.difference(known_addr)
            for addr in to_delete:
                self._remove_device(addr)
            for d in response['devices']:
                device = Device(dict(d))
                self._set_device(device)
        elif response.msg == 0x8045:  # endpoint list
            addr = response['addr']
            for endpoint in response['endpoints']: 
                self.simple_descriptor_request(addr, endpoint['endpoint'])
        elif response.msg == 0x8048:  # leave
            d = self.get_device_from_ieee(response['ieee'])
            if d:
                self._remove_device(d.addr)
        elif response.msg in (0x8100, 0x8102, 0x8110):  # attribute report
            device = self._get_device(response['addr'])
            added = device.update_endpoint(response['endpoint'], response.cleaned_data())
            changed = device.get_attribute(response['endpoint'], response['cluster'], response['attribute'])
            if added:
                dispatcher.send(ZIGATE_ATTRIBUTE_ADDED, self, **{'zigate': self,
                                                         'device': device,
                                                         'attribute': changed})
            dispatcher.send(ZIGATE_ATTRIBUTE_UPDATED, self, **{'zigate': self,
                                                         'device': device,
                                                         'attribute': changed})
        elif response.msg == 0x004D:  # device announce
            device = Device(response.data)
            self._set_device(device)
        else:
            LOGGER.debug('Do nothing special for response {}'.format(response))

    def _get_device(self, addr):
        '''
        get device from addr
        create it if necessary
        '''
        d = self.get_device_from_addr(addr)
        if not d:
            LOGGER.warning('Device not found, create it (this isn\'t normal)')
            d = Device({'addr': addr})
            self._set_device(d)
            self.get_devices_list()  # since device is missing, request info
        return d

    def _remove_device(self, addr):
        '''
        remove device from addr
        '''
        del self._devices[addr]
        dispatcher.send(ZIGATE_DEVICE_REMOVED, **{'zigate': self,
                                                  'addr': addr})

    def _set_device(self, device):
        '''
        add/update device to cache list
        '''
        assert type(device) == Device
        if device.addr in self._devices:
            self._devices[device.addr].update(device)
            dispatcher.send(ZIGATE_DEVICE_UPDATED, self, **{'zigate': self,
                                                      'device':self._devices[device.addr]})
        else:
            self._devices[device.addr] = device
            dispatcher.send(ZIGATE_DEVICE_ADDED, self, **{'zigate': self,
                                                    'device': device})
            self.active_endpoint_request(device.addr)

    def read_attribute(self, addr, endpoint, cluster_id, attribute_id):
        """
        Sends read attribute command to device

        :param str device_address: length 4. Example "AB01"
        :param str device_endpoint: length 2. Example "01"
        :param str cluster_id: length 4. Example "0000"
        :param str attribute_id: length 4. Example "0005"

        Examples:
        ========
        Replace device_address AB01 with your devices address.
        All clusters and parameters are not available on every device.
        - Get device manufacturer name: read_attribute('AB01', '01', '0000', '0004')
        - Get device name: read_attribute('AB01', '01', '0000', '0005')
        - Get device battery voltage: read_attribute('AB01', '01', '0001', '0006')
        """
        if isinstance(endpoint, int):
            endpoint = '{:04x}'.format(endpoint)
        cmd = '02' + addr + '01' + endpoint + cluster_id + '00 00 0000 01' + attribute_id
        self.send_data(0x0100, cmd)

    def read_multiple_attributes(self, addr, endpoint, cluster_id, first_attribute_id, attributes):
        """
        Constrcts read_attribute command with multiple attributes and sends it

        :param str device_address: length 4. E
        :param str device_endpoint: length 2.
        :param str cluster_id: length 4.
        :param str first_attribute_id: length 4
        :param int attributes: How many attributes are requested. Max value 255

        Examples:
        ========
        Replace device_address AB01 with your devices address.
        All clusters and parameters are not available on every device.

        - Get five first attributes from "General: Basic" cluster:
          read_multiple_attributes('AB01', '01', '0000', '0000', 5)
        """
        if isinstance(endpoint, int):
            endpoint = '{:04x}'.format(endpoint)
        cmd = '02' + addr + '01' + endpoint + cluster_id + '00 00 0000' + '{:02x}'.format(attributes)
        for i in range(attributes):
            cmd += '{:04x}'.format(int(first_attribute_id, 16) + i)
        self.send_data(0x0100, cmd)

    def get_status_text(self, status_code):
        return STATUS_CODES.get(status_code,
                                'Failed with event code: {}'.format(status_code))

    def _clear_response(self, msg_type):
        if msg_type in self._last_response:
            del self._last_response[msg_type]

    def _wait_response(self, msg_type):
        '''
        wait for next msg_type response
        '''
        LOGGER.debug('Waiting for message 0x{:04x}'.format(msg_type))
        t1 = time()
        while self._last_response.get(msg_type) is None:
            sleep(0.01)
            t2 = time()
            if t2-t1 > 3:  # no response timeout
                LOGGER.error('No response waiting command 0x{:04x}'.format(msg_type))
                return
        LOGGER.debug('Stop waiting, got message 0x{:04x}'.format(msg_type))
        return self._last_response.get(msg_type)

    def _wait_status(self, cmd):
        '''
        wait for status of cmd
        '''
        LOGGER.debug('Waiting for status message for command 0x{:04x}'.format(cmd))
        t1 = time()
        while self._last_status.get(cmd) is None:
            sleep(0.01)
            t2 = time()
            if t2-t1 > 3:  # no response timeout
                LOGGER.error('No response after command 0x{:04x}'.format(cmd))
                return
        LOGGER.debug('STATUS code to command 0x{:04x}:{}'.format(cmd, self._last_status.get(cmd)))
        return self._last_status.get(cmd)

    @property
    def devices(self):
        return list(self._devices.values())

    def get_device_from_addr(self, addr):
        return self._devices.get(addr)

    def get_device_from_ieee(self, ieee):
        for d in self._devices.values():
            if d['ieee'] == ieee:
                return d

    def get_devices_list(self, wait=False):
        '''
        refresh device list from zigate
        '''
        wait_response = None
        if wait:
            wait_response = 0x8015
        self.send_data(0x0015, wait_response=wait_response)

    def get_version(self, refresh=False):
        '''
        get zigate firmware version
        '''
        if not self._version or refresh:
            self._version = self.send_data(0x0010, wait_response=0x8010).data
        return self._version

    def get_version_text(self, refresh=False):
        '''
        get zigate firmware version as text
        '''
        v = self.get_version(refresh)['version']
        return v

    def reset(self):
        '''
        reset zigate
        '''
        return self.send_data(0x0011)

    def erase_persistent(self):
        '''
        erase persistent data in zigate
        '''
        return self.send_data(0x0012)
        # todo, erase local persitent

    def is_permitting_join(self):
        '''
        check if zigate is permitting join
        '''
        r = self.send_data(0x0014, wait_response=0x8014)
        if r:
            r = r.get('status', False)
        return r

    def permit_join(self, duration=30):
        '''
        start permit join
        '''
        return self.send_data(0x0049, 'FFFC{:02X}00'.format(duration))

    def set_channel(self, channels=None):
        '''
        set channel
        '''
        channels = channels or [11, 14, 15, 19, 20, 24, 25]
        if not isinstance(channels, list):
            channels = [channels]
        mask = functools.reduce(lambda acc, x: acc ^ 2 ** x, channels, 0)
        mask = '{:08X}'.format(mask)
        return self.send_data(0x0021, mask)

    def set_type(self, typ=TYPE_COORDINATOR):
        '''
        set zigate mode type
        '''
        self.send_data(0x0023, typ)

    def start_network(self):
        ''' start network '''
        return self.send_data(0x0024)
#         return self._wait_response(b'8024')

    def start_network_scan(self):
        ''' start network scan '''
        return self.send_data(0x0025)

    def remove_device(self, addr):
        ''' remove device '''
        return self.send_data(0x0026, addr)

    def simple_descriptor_request(self, addr, endpoint):
        '''
        simple_descriptor_request
        '''
        if isinstance(endpoint, int):
            endpoint = '{:04x}'.format(endpoint)
        return self.send_data(0x0043, addr+endpoint)

    def power_descriptor_request(self, addr):
        '''
        power descriptor request
        '''
        return self.send_data(0x0044, addr)

    def active_endpoint_request(self, addr):
        '''
        active endpoint request
        '''
        return self.send_data(0x0045, addr)


class ZiGateWiFi(ZiGate):
    def __init__(self, host, port=9999, path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True):
        self._host = host
        ZiGate.__init__(self, port=port, path=path,
                        auto_start=auto_start,
                        auto_save=auto_save
                        )

    def setup_connection(self):
        self.connection = ThreadSocketConnection(self, self._host, self._port)


class DeviceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Device):
            return obj.to_json()
        elif isinstance(obj, bytes):
            return hexlify(obj).decode()
        return json.JSONEncoder.default(self, obj)


class Device(object):
    def __init__(self, info=None):
        self.info = info or {}
        self.endpoints = {}

    def update(self, device):
        '''
        update from other device
        '''
        self.info.update(device.info)
        self.endpoints.update(device.endpoints)
        self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self._analyse()

    def update_endpoint(self, endpoint, data):
        '''
        update endpoint from dict
        '''
        added = False
        if endpoint not in self.endpoints:
            self.endpoints[endpoint] = {}
        cluster = data['cluster']
        attribute = data['attribute']
        rssi = data.pop('rssi', 0)
        if rssi > 0:
            self.info['link_quality'] = rssi
        key = '{:04x}_{:04x}'.format(cluster, attribute)
        if key not in self.endpoints[endpoint]:
            added = True
            self.endpoints[endpoint][key] = {}
        self.endpoints[endpoint][key].update(data)
        self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self._analyse()
        return added

    @property
    def addr(self):
        return self.info['addr']

    @staticmethod
    def from_json(data):
        d = Device()
        d.info = data.get('info', {})
        for endpoint in data.get('endpoints', []):
            d.endpoints[endpoint['endpoint']] = endpoint['attributes']
        return d

    def to_json(self):
        return {'addr': self.addr,
                'info': self.info,
                'endpoints': [{'endpoint': k, 'attributes': v}
                              for k, v in self.endpoints.items()],
                }

    def set_property(self, property_id, property_data, endpoint=None):
        if endpoint is None:
            self.info[property_id] = property_data
        else:
            if endpoint not in self.endpoints:
                self.endpoints[endpoint] = {}
            self.endpoints[endpoint][property_id] = property_data

    def __str__(self):
        name = ''
        typ = self.get_property('type')
        if typ:
            name = typ['value']
        return 'Device {} {}'.format(self.addr, name)

    def __repr__(self):
        return self.__str__()

    def __setitem__(self, key, value):
        self.info[key] = value

    def __getitem__(self, key):
        return self.info[key]

    def __delitem__(self, key):
        return self.info.__delitem__(key)

    def get(self, key, default):
        return self.info.get(key, default)

    def __contains__(self, key):
        return self.info.__contains__(key)

    def __len__(self):
        return len(self.info)

    def __iter__(self):
        return self.info.__iter__()

    def items(self):
        return self.info.items()

    def keys(self):
        return self.info.keys()

    def __getattr__(self, attr):
        return self.info[attr]

    @property
    def properties(self):
        '''
        well known attribute
        attribute with friendly name
        '''
        for attributes in self.endpoints.values():
            for attribute in attributes.values():
                if 'friendly_name' in attribute:
                    yield attribute

    def get_property(self, friendly_name):
        '''
        return attribute matching friendly_name
        '''
        for attributes in self.endpoints.values():
            for attribute in attributes.values():
                if attribute.get('friendly_name') == friendly_name:
                    return attribute

    def get_attribute(self, endpoint, cluster, attribute):
        key = '{:04x}_{:04x}'.format(cluster, attribute)
        return self.endpoints[endpoint][key]

    def _analyse(self, attributes_list=None):
        '''
        analyse endpoint to create friendly attribute name
        and better value decoding
        '''
        if not attributes_list:
            attributes_list = self.endpoints.values()
        for attributes in attributes_list:
            for attribute in attributes.values():
                key = (attribute.get('cluster'), attribute.get('attribute'))
                if key in ATTRIBUTES:
                    v = ATTRIBUTES[key]
                    attribute.update(v)
                    value = attribute['data']
                    attribute['value'] = eval(attribute['value'])
