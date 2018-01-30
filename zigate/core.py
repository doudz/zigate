#! /usr/bin/python3
from binascii import (hexlify, unhexlify)
from time import (sleep, strftime, time)
from collections import OrderedDict
import logging
import json
import os
from .transport import (ThreadSerialConnection, ThreadSocketConnection)
from .response import (RESPONSES, Response)
import functools
import struct
import threading

LOGGER = logging.getLogger('zigate')

CLUSTERS = {b'0000': 'General: Basic',
            b'0001': 'General: Power Config',
            b'0002': 'General: Temperature Config',
            b'0003': 'General: Identify',
            b'0004': 'General: Groups',
            b'0005': 'General: Scenes',
            b'0006': 'General: On/Off',
            b'0007': 'General: On/Off Config',
            b'0008': 'General: Level Control',
            b'0009': 'General: Alarms',
            b'000A': 'General: Time',
            b'000F': 'General: Binary Input Basic',
            b'0020': 'General: Poll Control',
            b'0019': 'General: OTA',
            b'0101': 'General: Door Lock',
            b'0201': 'HVAC: Thermostat',
            b'0202': 'HVAC: Fan Control',
            b'0300': 'Lighting: Color Control',
            b'0400': 'Measurement: Illuminance',
            b'0402': 'Measurement: Temperature',
            b'0403': 'Measurement: Atmospheric Pressure',
            b'0405': 'Measurement: Humidity',
            b'0406': 'Measurement: Occupancy Sensing',
            b'0500': 'Security & Safety: IAS Zone',
            b'0702': 'Smart Energy: Metering',
            b'0B05': 'Misc: Diagnostics',
            b'1000': 'ZLL: Commissioning',
            b'FF01': 'Xiaomi private',
            b'FF02': 'Xiaomi private',
            b'1234': 'Xiaomi private'
            }

ZGT_LOG_LEVELS = ['Emergency', 'Alert', 'Critical', 'Error',
                  'Warning', 'Notice', 'Information', 'Debug']

STATUS_CODES = {0: 'Success', 1: 'Invalid parameters',
                2: 'Unhandled command', 3: 'Command failed',
                4: 'Busy', 5: 'Stack already started'}

# states & properties
ZGT_TEMPERATURE = 'temperature'
ZGT_PRESSURE = 'pressure'
ZGT_DETAILED_PRESSURE = 'detailed pressure'
ZGT_HUMIDITY = 'humidity'
ZGT_LAST_SEEN = 'last_seen'
ZGT_EVENT = 'event'
ZGT_EVENT_PRESENCE = 'presence detected'
ZGT_STATE = 'state'
ZGT_STATE_ON = 'on-press'
ZGT_STATE_OFF = 'off-release'
ZGT_STATE_MULTI = 'multi_{}'

# commands for external use
ZGT_CMD_NEW_DEVICE = 'new_device'
ZGT_CMD_DEVICE_UPDATE = 'device_update'
ZGT_CMD_LIST_ENDPOINTS = 'list_endpoints'
ZGT_CMD_REMOVE_DEVICE = 'remove_device'

BATTERY = 0
AC_POWER = 1

TYPE_COORDINATOR = '00'
TYPE_ROUTER = '01'
TYPE_LEGACY_ROUTER = '02'

AUTO_SAVE = 5*60  # 5 minutes


class ZiGate(object):

    def __init__(self, port='auto', path='~/.zigate.json',
                 callback=None,
                 auto_start=True,
                 auto_save=True):
        self._buffer = b''
        self._devices = {}
        self._path = path
        self._version = None
        self._callback = callback
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
            logging.error('Exception during closing {}'.format(e))

    def save_state(self, path=None):
        self._save_lock.acquire()
        path = path or self._path
        self._path = os.path.expanduser(path)
        with open(self._path, 'w') as fp:
            json.dump(list(self._devices.values()), fp, cls=DeviceEncoder)
        self._save_lock.release()

    def load_state(self, path=None):
        path = path or self._path
        self._path = os.path.expanduser(path)
        if os.path.exists(self._path):
            with open(self._path) as fp:
                devices = json.load(fp, object_pairs_hook=OrderedDict)
            for data in devices:
                device = Device.from_json(data)
                self._devices[device.addr] = device
            return True
        return False

    def start_auto_save(self):
        logging.debug('Auto saving {}'.format(self._path))
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
        self.get_devices_list()

    def zigate_encode(self, data):
        """encode all characters < 0x02 to avoid """
        encoded = []
        for x in data:
            if x < 0x10:
                encoded.append(0x02)
                encoded.append(x ^ 0x10)
            else:
                encoded.append(x)

        return encoded

    def zigate_decode2(self, data):
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

    @staticmethod
    def zigate_decode(data):
        """reverse of zigate_encode to get back the real message"""
        encoded = False
        decoded_data = b''

        def bxor_join(b1, b2):  # use xor for bytes
            parts = []
            for b1, b2 in zip(b1, b2):
                parts.append(bytes([b1 ^ b2]))
            return b''.join(parts)

        for x in data:
            if bytes([x]) == b'\x02':
                encoded = True
            elif encoded is True:
                encoded = False
                decoded_data += bxor_join(bytes([x]), b'\x10')
            else:
                decoded_data += bytes([x])

        return decoded_data

    def checksum2(self, *args):
        chcksum = 0
        for arg in args:
            if isinstance(arg, int):
                chcksum ^= arg
                continue
            for x in arg:
                chcksum ^= x
        return chcksum

    @staticmethod
    def checksum(cmd, length, data):
        tmp = 0
        tmp ^= cmd[0]
        tmp ^= cmd[1]
        tmp ^= length[0]
        tmp ^= length[1]
        if data:
            for x in data:
                tmp ^= x

        return tmp

    # register valuable (i.e. non technical properties) for futur use
    def set_device_property(self, addr, property_id, property_data, endpoint=None):
        """
        log property / attribute value in a device based dictionnary
        please note that short addr is not stable if device is reset
        (still have to find the unique ID)
        all data stored must be directly usable (i.e no bytes)
        """
        str_addr = addr.decode()
        if str_addr not in self._devices:
            self._devices[str_addr] = Device(str_addr)
        self._devices[str_addr].set_property(property_id, property_data, endpoint)
        self.call_callback(ZGT_CMD_DEVICE_UPDATE,
                           device=self._devices[str_addr],
                           change={'property_id': property_id,
                                   'property_data': property_data,
                                   'endpoint': endpoint})
#         self._devices[str_addr][property_id] = property_data

    def set_callback(self, func):
        '''
        external func, must accept two args
        command_type and option kwargs
        func(command_type, **kwargs)
        '''
        self._callback = func

    def call_callback(self, command_type, **kwargs):
        logging.debug('CALLBACK {} {}'.format(command_type,kwargs))
        if self._callback:
            self._callback(command_type, **kwargs)

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
            self.decode_data2(raw_message)
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    def send_data(self, cmd, data=""):
        '''
        send data through ZiGate
        '''
        self._last_status[cmd] = None
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

        # --- non encoded version ---
        std_msg = [0x01]
        std_msg.extend(byte_cmd)
        std_msg.extend(byte_length)
        std_msg.append(self.checksum(byte_cmd, byte_length, byte_data))
        if data != "":
            std_msg.extend(byte_data)
        std_msg.append(0x03)

        # --- encoded version ---
        enc_msg = [0x01]
        enc_msg.extend(self.zigate_encode(byte_cmd))
        enc_msg.extend(self.zigate_encode(byte_length))
        enc_msg.append(self.checksum(byte_cmd, byte_length, byte_data))
        if data != "":
            enc_msg.extend(self.zigate_encode(byte_data))
        enc_msg.append(0x03)

        std_output = b''.join([bytes([x]) for x in std_msg])
        encoded_output = b''.join([bytes([x]) for x in enc_msg])
        LOGGER.debug('--------------------------------------')
        LOGGER.debug('REQUEST      : 0x{:04x} {}'.format(cmd, data))
        LOGGER.debug('  # standard : {}'.format(' '.join([format(x, '02x') for x in std_output]).upper()))
        LOGGER.debug('  # encoded  : {}'.format(hexlify(encoded_output)))
        LOGGER.debug('--------------------------------------')

        self.send_to_transport(encoded_output)
        status = self._wait_status(cmd)
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

    def decode_data2(self, raw_message):
        decoded = self.zigate_decode2(raw_message)
        msg_type, length, checksum, value, rssi = \
            struct.unpack('!HHB%dsB' % (len(decoded) - 6), decoded)
        if length != len(value)+1:  # add rssi length
            LOGGER.error('Bad length {} != {} : {}'.format(length,
                                                           len(value),
                                                           value))
            return
        computed_checksum = self.checksum2(decoded[:4], rssi, value)
        if checksum != computed_checksum:
            LOGGER.error('Bad checksum {} != {}'.format(checksum,
                                                        computed_checksum))
            return
        response = RESPONSES.get(msg_type, Response)(value, rssi)
        LOGGER.debug(response)
        self._last_response[msg_type] = response
        self.interpret_response(response)

    def interpret_response(self, response):
        if response.msg == 0x8000:  # status
            if response['status'] != 0:
                logging.error('Command {} failed {} : {}'.format(response['packet_type'],
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
        elif response.msg == 0x8048:  # leave
            d = self.get_device_from_ieee(response['ieee'])
            if d:
                self._remove_device(d.addr)
        elif response.msg in (0x8100, 0x8102, 0x8110):  # attribute report
            device = self._get_device(response['addr'])
            data = response.cleaned_data()
            device.update_endpoint(response['endpoint'], data)
            self.call_callback(ZGT_CMD_DEVICE_UPDATE, device=device, change=data)
        elif response.msg == 0x004D:  # device announce
            device = Device(response.data)
            self._set_device(device)
            

    def _get_device(self, addr):
        '''
        get device from addr
        create it if necessary
        '''
        d = self.get_device_from_addr(addr)
        if not d:
            logging.debug('not found,create')
            d = Device({'addr': addr})
            self._set_device(d)
            self.get_devices_list()  # since device is missing, request info
        return d

    def _remove_device(self, addr):
        '''
        remove device from addr
        '''
        del self._devices[addr]
        self.call_callback(ZGT_CMD_REMOVE_DEVICE, addr=addr)

    def _set_device(self, device):
        '''
        add/update device to cache list
        '''
        assert type(device) == Device
        if device.addr in self._devices:
            self._devices[device.addr].update(device)
            self.call_callback(ZGT_CMD_DEVICE_UPDATE,
                               device=self._devices[device.addr])
        else:
            self._devices[device.addr] = device
            self.call_callback(ZGT_CMD_NEW_DEVICE, device=device)
            self.active_endpoint_request(device.addr)

    def decode_data(self, data):
        """Interpret responses attributes"""
        msg_data = data[5:]
        msg_type = hexlify(data[0:2])
        msg = msg_data

        self._last_response[msg_type] = None

        # Do different things based on MsgType
        LOGGER.debug('--------------------------------------')
        # Device Announce
        if msg_type == b'004d':
            strct = OrderedDict([('short_addr', 16), ('mac_addr', 64),
                                  ('mac_capability', 'rawend')])
            msg = self.decode_struct(strct, msg_data)
            addr = msg['short_addr'].decode()
            self.call_callback(ZGT_CMD_NEW_DEVICE,
                                      addr=addr)
            self.set_device_property(msg['short_addr'], 'MAC',
                                     msg['mac_addr'].decode())

            LOGGER.debug('RESPONSE 004d : Device Announce')
            LOGGER.debug('  * From address   : {}'.format(msg['short_addr']))
            LOGGER.debug('  * MAC address    : {}'.format(msg['mac_addr']))
            LOGGER.debug('  * MAC capability : {}'.
                          format(msg['mac_capability']))

            time.sleep(1)
            self.active_endpoint_request(addr)

        # Status
        elif msg_type == b'8000':
            strct = OrderedDict([('status', 'int'), ('sequence', 8),
                                  ('packet_type', 16), ('info', 'rawend')])
            msg = self.decode_struct(strct, msg_data)

            status_text = self.get_status_text(msg['status'])

            LOGGER.debug('RESPONSE 8000 : Status')
            LOGGER.debug('  * Status              : {}'.format(status_text))
            LOGGER.debug('  - Sequence            : {}'.format(msg['sequence']))
            LOGGER.debug('  - Response to command : {}'.format(msg['packet_type']))
            if hexlify(msg['info']) != b'00':
                LOGGER.debug('  - Additional msg: ', msg['info'])
#             self._last_status[struct.unpack('!H',unhexlify(msg['packet_type']))[0]] = msg['status']

        # Default Response
        elif msg_type == b'8001':
            strct = OrderedDict([('level', 'int'), ('info', 'rawend')])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8001 : Log Message')
            LOGGER.debug('  - Log Level : {}'.format(ZGT_LOG_LEVELS[msg['level']]))
            LOGGER.debug('  - Log Info  : {}'.format(msg['info']))

        # Object Clusters list
        elif msg_type == b'8003':
            strct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_list', 16)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8003 : Object Clusters list')
            LOGGER.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            LOGGER.debug('  - cluster_list  : {}'.format(msg['cluster_list']))

        # Object attributes list
        elif msg_type == b'8004':
            strct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_id', 16), ('attribute',16)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8004 : Object attributes list')
            LOGGER.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            LOGGER.debug('  - Cluster ID  : {}'.format(msg['cluster_id']))
            LOGGER.debug('  - Attributes  : {}'.format(msg['attribute']))

        # Object Commands list
        elif msg_type == b'8005':
            strct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_id', 16), ('command',8)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8005 : Object Commands list')
            LOGGER.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            LOGGER.debug('  - Cluster ID  : {}'.format(msg['cluster_id']))
            LOGGER.debug('  - Commands  : {}'.format(msg['command']))

        # “Factory New” Restart
        elif msg_type == b'8007':
            strct = OrderedDict([('status', 'int')])
            msg = self.decode_struct(strct, msg_data)
            status_codes = {0:'STARTUP', 2:'NFN_START', 6:'RUNNING'}
            LOGGER.debug('RESPONSE 8007 : “Factory New” Restart')
            LOGGER.debug('  - Status  : {} - {}'.format(msg['status'],
                                                            status_codes.get(msg['status'],
                                                                             'unknown status')))

        # Version List
        elif msg_type == b'8010':
            strct = OrderedDict([('major', 'int16'), ('installer', 'int16')])
            msg = self.decode_struct(strct, msg_data)
            LOGGER.debug('RESPONSE 8010 : Version List')
            LOGGER.debug('  - Major version     : {}'.format(msg['major']))
            LOGGER.debug('  - Installer version : {}'.format(msg['installer']))

        # permt join status
        elif msg_type == b'8014':
            strct = OrderedDict([('status', 'bool')])
            msg = self.decode_struct(strct, msg_data)
            LOGGER.debug('RESPONSE 8014 : Permit join status')
            LOGGER.debug('  - Status     : {}'.format(msg['status']))

        # device list
        elif msg_type == b'8015':
            strct = OrderedDict([('length', 'int8'),('device_list', 13),])
            msg = self.decode_struct(strct, msg_data)
            LOGGER.debug('RESPONSE 8015 : Device list')
            LOGGER.debug('  - Nb devices     : {}'.format(msg['length']))

        # Network joined / formed
        elif msg_type == b'8024':
            strct = OrderedDict([('status', 8), ('short_addr', 16), 
                                  ('mac_addr', 64), ('channel', 'int')])
            msg = self.decode_struct(strct, msg_data)
            LOGGER.debug('RESPONSE 8024 : Network joined / formed')
            LOGGER.debug('  - Status     : {}'.format(msg['status']))
            LOGGER.debug('  - Short address   : {}'.format(msg['short_addr']))
            LOGGER.debug('  - MAC address    : {}'.format(msg['mac_addr']))
            LOGGER.debug('  - Channel    : {}'.format(msg['channel']))

        # Node Descriptor
        elif msg_type == b'8042':
            strct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('manufacturer_code', 16),
                                  ('max_rx', 16), ('max_tx', 16),
                                  ('server_mask', 16),
                                  ('descriptor_capability', 8),
                                  ('mac_flags', 8), ('max_buffer_size', 16),
                                  ('bit_field', 16)])
            msg = self.decode_struct(strct, msg_data)

            server_mask_binary = format(int(msg['server_mask'], 16), '016b')
            descriptor_capability_binary = format(int(msg['descriptor_capability'], 16), '08b')
            mac_flags_binary = format(int(msg['mac_flags'], 16), '08b')
            bit_field_binary = format(int(msg['bit_field'], 16), '016b')

            # Length 16, 7-15 Reserved
            server_mask_desc = ['Primary trust center',
                                'Back up trust center',
                                'Primary binding cache',
                                'Backup binding cache',
                                'Primary discovery cache',
                                'Backup discovery cache',
                                'Network manager']
            # Length 8, 2-7 Reserved
            descriptor_capability_desc = ['Extended Active endpoint list',
                                          'Extended simple descriptor list']
            # Length 8
            mac_capability_desc = ['Alternate PAN Coordinator', 'Device Type',
                                   'Power source', 'Receiver On when Idle',
                                   'Reserved', 'Reserved',
                                   'Security capability', 'Allocate Address']
            # Length 16
            bit_field_desc = ['Logical type: Coordinator',
                              'Logical type: Router',
                              'Logical type: End Device',
                              'Complex descriptor available',
                              'User descriptor available', 'Reserved',
                              'Reserved', 'Reserved',
                              'APS Flag', 'APS Flag', 'APS Flag',
                              'Frequency band', 'Frequency band',
                              'Frequency band', 'Frequency band',
                              'Frequency band']

            LOGGER.debug('RESPONSE 8042 : Node Descriptor')
            LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            LOGGER.debug('  - Status            : {}'.format(msg['status']))
            LOGGER.debug('  - From address      : {}'.format(msg['addr']))
            LOGGER.debug('  - Manufacturer code : {}'.format(msg['manufacturer_code']))
            LOGGER.debug('  - Max Rx size       : {}'.format(msg['max_rx']))
            LOGGER.debug('  - Max Tx size       : {}'.format(msg['max_tx']))
            LOGGER.debug('  - Server mask       : {}'.format(msg['server_mask']))
            LOGGER.debug('    - Binary          : {}'.format(server_mask_binary))
            for i, description in enumerate(server_mask_desc, 1):
                LOGGER.debug('    - %s : %s' % (description, 'Yes' if server_mask_binary[-i] == '1' else 'No'))
            LOGGER.debug('  - Descriptor        : {}'.format(msg['descriptor_capability']))
            LOGGER.debug('    - Binary          : {}'.format(descriptor_capability_binary))
            for i, description in enumerate(descriptor_capability_desc, 1):
                LOGGER.debug('    - %s : %s' %
                              (description, 'Yes' if descriptor_capability_binary[-i] == '1' else 'No'))
            LOGGER.debug('  - Mac flags         : {}'.format(msg['mac_flags']))
            LOGGER.debug('    - Binary          : {}'.format(mac_flags_binary))
            for i, description in enumerate(mac_capability_desc, 1):
                LOGGER.debug('    - %s : %s' % (description, 'Yes'if mac_flags_binary[-i] == '1' else 'No'))
            LOGGER.debug('  - Max buffer size   : {}'.format(msg['max_buffer_size']))
            LOGGER.debug('  - Bit field         : {}'.format(msg['bit_field']))
            LOGGER.debug('    - Binary          : {}'.format(bit_field_binary))
            for i, description in enumerate(bit_field_desc, 1):
                LOGGER.debug('    - %s : %s' % (description, 'Yes' if bit_field_binary[-i] == '1' else 'No'))

        # Cluster List
        elif msg_type == b'8043':
            strct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('length', 8), ('endpoint', 8),
                                  ('profile', 16), ('device_id', 16),
                                  ('bit', 8), ('in_cluster_count', 'count'),
                                  ('in_cluster_list', 16),
                                  ('out_cluster_count', 'count'),
                                  ('out_cluster_list', 16)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8043 : Cluster List')
            LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            LOGGER.debug('  - Status            : {}'.format(msg['status']))
            LOGGER.debug('  - From address      : {}'.format(msg['addr']))
            LOGGER.debug('  - Length            : {}'.format(msg['length']))
            LOGGER.debug('  - EndPoint          : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Profile ID        : {}'.format(msg['profile']))
            LOGGER.debug('  - Device ID         : {}'.format(msg['device_id']))
            LOGGER.debug('  - IN cluster count  : {}'.format(msg['in_cluster_count']))
            for i, cluster_id in enumerate(msg['in_cluster_list']):
                LOGGER.debug('    - Cluster %s : %s (%s)' % (i, cluster_id, CLUSTERS.get(cluster_id, 'unknown')))
            LOGGER.debug('  - OUT cluster count  : {}'.format(msg['out_cluster_count']))
            for i, cluster_id in enumerate(msg['out_cluster_list']):
                LOGGER.debug('    - Cluster %s : %s (%s)' % (i, cluster_id, CLUSTERS.get(cluster_id, 'unknown')))

        # Power Descriptor
        elif msg_type == b'8044':
            strct = OrderedDict([('sequence', 8), ('status', 8),
                                 ('bit_field', 16), ])
            msg = self.decode_struct(strct, msg_data)

            bit_field_binary = format(int(msg['bit_field'], 16), '016b')

            # Others Reserved
            power_mode_desc = {'0000': 'Receiver on when idle',
                               '0001': 'Receiver switched on periodically',
                               '0010': 'Receiver switched on when stimulated,'}
            power_sources = ['Permanent mains supply', 'Rechargeable battery',
                             'Disposable battery']  # 4th Reserved
            current_power_level = {'0000': 'Critically low',
                                   '0100': 'Approximately 33%',
                                   '1000': 'Approximately 66%',
                                   '1100': 'Approximately 100%'}

            LOGGER.debug('RESPONSE 8044 : Power Descriptor')
            LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            LOGGER.debug('  - Status            : {}'.format(msg['status']))
            LOGGER.debug('  - Bit field         : {}'.format(msg['bit_field']))
            LOGGER.debug('    - Binary          : {}'.format(bit_field_binary))
            LOGGER.debug('    - Current mode    : {}'.format(
                power_mode_desc.get(bit_field_binary[-4:], 'Unknown')))
            LOGGER.debug('    - Sources         : ')
            for i, description in enumerate(power_sources, 1):
                LOGGER.debug('       - %s : %s %s' %
                              (description,
                               'Yes' if bit_field_binary[8:12][-i] == '1' else 'No',
                               '[CURRENT]' if bit_field_binary[4:8][-i] == '1'else '')
                              )
            LOGGER.debug('    - Level           : {}'.format(
                current_power_level.get(bit_field_binary[:4], 'Unknown')))

        # Endpoint List
        elif msg_type == b'8045':
            strct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('endpoint_count', 'count'),
                                  ('endpoint_list', 8)])
            msg = self.decode_struct(strct, msg_data)
            endpoints = [elt.decode() for elt in msg['endpoint_list']]
            self.set_device_property(msg['addr'], 'endpoints', endpoints)
            self.call_callback(ZGT_CMD_LIST_ENDPOINTS, addr=msg['addr'].decode(), endpoints=endpoints)

            LOGGER.debug('RESPONSE 8045 : Active Endpoints List')
            LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            LOGGER.debug('  - Status         : {}'.format(msg['status']))
            LOGGER.debug('  - From address   : {}'.format(msg['addr']))
            LOGGER.debug('  - EndPoint count : {}'.
                          format(msg['endpoint_count']))
            for i, endpoint in enumerate(msg['endpoint_list']):
                LOGGER.debug('    * EndPoint %s : %s' % (i, endpoint))

        # Leave indication
        elif msg_type == b'8048':
            strct = OrderedDict([('extended_addr', 64), ('rejoin_status', 8)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8048 : Leave indication')
            LOGGER.debug('  - From address   : {}'.format(msg['extended_addr']))
            LOGGER.debug('  - Rejoin status  : {}'.format(msg['rejoin_status']))

        # Default Response
        elif msg_type == b'8101':
            strct = OrderedDict([('sequence', 8), ('endpoint', 8),
                                 ('cluster', 16), ('command_id', 8),
                                 ('status', 8)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8101 : Default Response')
            LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            LOGGER.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Cluster id     : {} ({})'.format(
                msg['cluster'], CLUSTERS.get(msg['cluster'], 'unknown')))
            LOGGER.debug('  - Command        : {}'.format(msg['command_id']))
            LOGGER.debug('  - Status         : {}'.format(msg['status']))

        # Read attribute response, Attribute report, Write attribute response
        # Currently only support Xiaomi sensors.
        # Other brands might calc things differently
        elif msg_type in (b'8100', b'8102', b'8110'):
            LOGGER.debug('RESPONSE %s : Attribute Report / Response' % msg_type.decode())
            self.interpret_attributes(msg_data)

        # Zone status change
        elif msg_type == b'8401':
            strct = OrderedDict([('sequence', 8), ('endpoint', 8),
                                 ('cluster', 16), ('src_address_mode', 8),
                                 ('src_address', 16), ('zone_status', 16),
                                 ('extended_status', 16), ('zone_id', 8),
                                 ('delay_count', 'count'), ('delay_list', 16)])
            msg = self.decode_struct(strct, msg_data)

            zone_status_binary = format(int(msg['zone_status'], 16), '016b')

            # Length 16, 10-15 Reserved
            zone_status_descs = ('Alarm 1', 'Alarm 2', 'Tampered',
                                 'Battery', 'Supervision reports',
                                 'Report when normal', 'Trouble',
                                 'AC (Mains)', 'Test Mode',
                                 'Battery defective')
            zone_status_values = (('Closed/Not alarmed', 'Opened/Alarmed'),
                                  ('Closed/Not alarmed', 'Opened/Alarmed'),
                                  ('No', 'Yes'), ('OK', 'Low'), ('No', 'Yes'),
                                  ('No', 'Yes'), ('No', 'Yes'),
                                  ('Ok', 'Failure'), ('No', 'Yes'),
                                  ('No', 'Yes'),)

            LOGGER.debug('RESPONSE 8401 : Zone status change notification')
            LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            LOGGER.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            LOGGER.debug('  - Cluster id     : {} ({})'.format(
                msg['cluster'], CLUSTERS.get(msg['cluster'], 'unknown')))
            LOGGER.debug('  - Src addr mode  : {}'.format(msg['src_address_mode']))
            LOGGER.debug('  - Src address    : {}'.format(msg['src_address']))
            LOGGER.debug('  - Zone status    : {}'.format(msg['zone_status']))
            LOGGER.debug('    - Binary       : {}'.format(zone_status_binary))
            for i, description in enumerate(zone_status_descs, 1):
                j = int(zone_status_binary[-i])
                LOGGER.debug('    - %s : %s' % (description, zone_status_values[i-1][j]))
            LOGGER.debug('  - Zone id        : {}'.format(msg['zone_id']))
            LOGGER.debug('  - Delay count    : {}'.format(msg['delay_count']))
            for i, value in enumerate(msg['delay_list']):
                LOGGER.debug('    - %s : %s' % (i, value))

        # Route Discovery Confirmation
        elif msg_type == b'8701':
            LOGGER.debug('RESPONSE 8701: Route Discovery Confirmation')
            LOGGER.debug('  - Sequence       : {}'.format(hexlify(msg_data[:1])))
            LOGGER.debug('  - Status         : {}'.format(hexlify(msg_data[1:2])))
            LOGGER.debug('  - Network status : {}'.format(hexlify(msg_data[2:3])))
            LOGGER.debug('  - Message data   : {}'.format(hexlify(msg_data)))

        # APS Data Confirm Fail
        elif msg_type == b'8702':
            strct = OrderedDict([('status', 8), ('src_endpoint', 8),
                                 ('dst_endpoint', 8), ('dst_address_mode', 8),
                                  ('dst_address', 64), ('sequence', 8)])
            msg = self.decode_struct(strct, msg_data)

            LOGGER.debug('RESPONSE 8702 : APS Data Confirm Fail')
            LOGGER.debug('  - Status         : {}'.format(msg['status']))
            LOGGER.debug('  - Src endpoint   : {}'.format(msg['src_endpoint']))
            LOGGER.debug('  - Dst endpoint   : {}'.format(msg['dst_endpoint']))
            LOGGER.debug('  - Dst mode       : {}'.format(msg['dst_address_mode']))
            LOGGER.debug('  - Dst address    : {}'.format(msg['dst_address']))
            LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))

        # No handling for this type of message
        else:
            LOGGER.debug('RESPONSE %s : Unknown Message' % msg_type.decode())
            LOGGER.debug('  - After decoding  : {}'.format(hexlify(data)))
            LOGGER.debug('  - MsgType         : {}'.format(msg_type))
            LOGGER.debug('  - MsgLength       : {}'.format(hexlify(data[2:4])))
            LOGGER.debug('  - ChkSum          : {}'.format(hexlify(data[4:5])))
            LOGGER.debug('  - Data            : {}'.format(hexlify(msg_data)))
            LOGGER.debug('  - RSSI            : {}'.format(hexlify(data[-1:])))

        self._last_response[msg_type] = msg

    def interpret_attributes(self, msg_data):
        strct = OrderedDict([('sequence', 8),
                              ('short_addr', 16),
                              ('endpoint', 8),
                              ('cluster_id', 16),
                              ('attribute_id', 16),
                              ('attribute_status', 8),
                              ('attribute_type', 8),
                              ('attribute_size', 'len16'),
                              ('attribute_data', 'raw'),
                              ('end', 'rawend')])
        msg = self.decode_struct(strct, msg_data)
        device_addr = msg['short_addr']
        endpoint = msg['endpoint'].decode()
        cluster_id = msg['cluster_id']
        attribute_id = msg['attribute_id']
        attribute_size = msg['attribute_size']
        attribute_data = msg['attribute_data']
        self.set_device_property(device_addr, ZGT_LAST_SEEN,
                                 strftime('%Y-%m-%d %H:%M:%S'))

        if msg['sequence'] == b'00':
            LOGGER.debug('  - Sensor type announce (Start after pairing 1)')
        elif msg['sequence'] == b'01':
            LOGGER.debug('  - Something announce (Start after pairing 2)')

        # Device type
        if cluster_id == b'0000':
            if attribute_id == b'0005':
                self.set_device_property(device_addr, 'type',
                                         attribute_data.decode(), endpoint)
                LOGGER.info(' * type : {}'.format(attribute_data))
            ## proprietary Xiaomi info including battery
            if attribute_id == b'ff01' and attribute_data != b'':
                strct = OrderedDict([('start', 16), ('battery', 16), ('end', 'rawend')])
                raw_info = unhexlify(self.decode_struct(strct, attribute_data)['battery'])
                battery_info = int(hexlify(raw_info[::-1]), 16)/1000
                self.set_device_property(device_addr, endpoint, 'battery', battery_info)
                LOGGER.info('  * Battery info')
                LOGGER.info('  * Value : {} V'.format(battery_info))
        # Button status
        elif cluster_id == b'0006':
            LOGGER.info('  * General: On/Off')
            if attribute_id == b'0000':
                if hexlify(attribute_data) == b'00':
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_ON, endpoint)
                    LOGGER.info('  * Closed/Taken off/Press')
                else:
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_OFF, endpoint)
                    LOGGER.info('  * Open/Release button')
            elif attribute_id == b'8000':
                clicks = int(hexlify(attribute_data), 16)
                self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_MULTI.format(clicks),
                                             endpoint)
                LOGGER.info('  * Multi click')
                LOGGER.info('  * Pressed: {} times'.format(clicks))
        # Movement
        elif cluster_id == b'000c':  # Unknown cluster id
            LOGGER.info('  * Rotation horizontal')
        elif cluster_id == b'0012':  # Unknown cluster id
            if attribute_id == b'0055':
                if hexlify(attribute_data) == b'0000':
                    LOGGER.info('  * Shaking')
                elif hexlify(attribute_data) == b'0055':
                    LOGGER.info('  * Rotating vertical')
                    LOGGER.info('  * Rotated: {}°'.
                                 format(int(hexlify(attribute_data), 16)))
                elif hexlify(attribute_data) == b'0103':
                    LOGGER.info('  * Sliding')
        # Temperature
        elif cluster_id == b'0402':
            temperature = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_TEMPERATURE, temperature, endpoint)
            LOGGER.info('  * Measurement: Temperature'),
            LOGGER.info('  * Value: {} °C'.format(temperature))
        # Atmospheric Pressure
        elif cluster_id == b'0403':
            LOGGER.info('  * Atmospheric pressure')
            pressure = int(hexlify(attribute_data), 16)
            if attribute_id == b'0000':
                self.set_device_property(device_addr, ZGT_PRESSURE, pressure, endpoint)
                LOGGER.info('  * Value: {} mb'.format(pressure))
            elif attribute_id == b'0010':
                self.set_device_property(device_addr,
                                         ZGT_DETAILED_PRESSURE, pressure/10, endpoint)
                LOGGER.info('  * Value: {} mb'.format(pressure/10))
            elif attribute_id == b'0014':
                LOGGER.info('  * Value unknown')
        # Humidity
        elif cluster_id == b'0405':
            humidity = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_HUMIDITY, humidity, endpoint)
            LOGGER.info('  * Measurement: Humidity')
            LOGGER.info('  * Value: {} %'.format(humidity))
        # Presence Detection
        elif cluster_id == b'0406':
            # Only sent when movement is detected
            if hexlify(attribute_data) == b'01':
                self.set_device_property(device_addr, ZGT_EVENT,
                                         ZGT_EVENT_PRESENCE, endpoint)
                LOGGER.debug('   * Presence detection')

        LOGGER.info('  FROM ADDRESS      : {}'.format(msg['short_addr']))
        LOGGER.debug('  - Source EndPoint : {}'.format(msg['endpoint']))
        LOGGER.debug('  - Cluster ID      : {}'.format(msg['cluster_id']))
        LOGGER.debug('  - Attribute ID    : {}'.format(msg['attribute_id']))
        LOGGER.debug('  - Attribute type  : {}'.format(msg['attribute_type']))
        LOGGER.debug('  - Attribute size  : {}'.format(msg['attribute_size']))
        LOGGER.debug('  - Attribute data  : {}'.format(
                                               hexlify(msg['attribute_data'])))

    def read_attribute(self, device_address, device_endpoint, cluster_id, attribute_id):
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
        cmd = '02' + device_address + '01' + device_endpoint + cluster_id + '00 00 0000 01' + attribute_id
        self.send_data(0x0100, cmd)

    def read_multiple_attributes(self, device_address, device_endpoint, cluster_id, first_attribute_id, attributes):
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
        cmd = '02' + device_address + '01' + device_endpoint + cluster_id + '00 00 0000' + '{:02x}'.format(attributes)
        for i in range(attributes):
            cmd += '{:04x}'.format(int(first_attribute_id, 16) + i)
        self.send_data(0x0100, cmd)

    def get_status_text(self, status_code):
        return STATUS_CODES.get(status_code,
                                'Failed with event code: {}'.format(status_code))

    def _wait_response(self, msg_type):
        '''
        wait for next msg_type response
        '''
        LOGGER.debug('Waiting for message 0x{:04x}'.format(msg_type))
        t1 = time()
        while self._last_response.get(msg_type) is None:
            sleep(0.01)
            t2 = time()
            if t2-t1 > 3: #no response timeout
                LOGGER.error('No response waiting command 0x{:04x}'.format(msg_type))
                return
        LOGGER.debug('Got message 0x{:04x}'.format(msg_type))
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
            if t2-t1 > 3: #no response timeout
                LOGGER.error('No response after command 0x{:04x}'.format(cmd))
                return
        LOGGER.debug('STATUS code to command 0x{:04x}:{}'.format(cmd, self._last_status.get(cmd)))
        return self._last_status.get(cmd)

    def list_devices(self):
        LOGGER.debug('-- DEVICE REPORT -------------------------')
        for addr in self._devices.keys():
            LOGGER.info('- addr : {}'.format(addr))
            for k, v in self._devices[addr].properties.items():
                LOGGER.info('    * {} : {}'.format(k, v))
        LOGGER.debug('-- DEVICE REPORT - END -------------------')
        return list(self._devices.values())

    @property
    def devices(self):
        return list(self._devices.values())

    def get_device_from_addr(self, addr):
        return self._devices.get(addr)

    def get_device_from_ieee(self, ieee):
        for d in self._devices.values():
            if d['ieee'] == ieee:
                return d

    def get_devices_list(self):
        self.send_data(0x0015)
#         self._wait_response(b'8015')

    def get_version(self, refresh=False):
        if not self._version or refresh:
            self.send_data(0x0010)
            self._version = self._wait_response(0x8010).data
        return self._version

    def get_version_text(self, refresh=False):
        v = self.get_version(refresh)['version']
        return v

    def reset(self):
        return self.send_data(0x0011)

    def erase_persistent(self):
        return self.send_data(0x0012)
        # todo, erase local persitent

    def is_permitting_join(self):
        self.send_data(0x0014)
        r = self._wait_response(0x8014)
        if r:
            r = r.get('status', False)
        return r

    def permit_join(self, duration=30):
        """permit join for 30 secs (1E)"""
        return self.send_data(0x0049, 'FFFC{:02X}00'.format(duration))

    def set_channel(self, channels=None):
        channels = channels or [11, 14, 15, 19, 20, 24, 25]
        if not isinstance(channels, list):
            channels = [channels]
        mask = functools.reduce(lambda acc, x: acc ^ 2 ** x, channels, 0)
        mask = '{:08X}'.format(mask)
        return self.send_data(0x0021, mask)

    def set_type(self, typ=TYPE_COORDINATOR):
        self.send_data(0x0023, typ)

    def start_network(self):
        return self.send_data(0x0024)
#         return self._wait_response(b'8024')

    def start_network_scan(self):
        return self.send_data(0x0025)

    def remove_device(self, addr):
        return self.send_data(0x0026, addr)

    def simple_descriptor_request(self, addr, endpoint):
        return self.send_data(0x0043, addr+endpoint)

    def active_endpoint_request(self, addr):
        return self.send_data(0x0045, addr)


class ZiGateWiFi(ZiGate):
    def __init__(self, host, port=9999, path='~/.zigate.json',
                 callback=None,
                 auto_start=True,
                 auto_save=True):
        self._host = host
        ZiGate.__init__(self, port=port, path=path, callback=callback,
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
            return obj.decode()
        return json.JSONEncoder.default(self, obj)


class Device(object):
    def __init__(self, properties={}, endpoints={}):
        self.properties = properties
        self.endpoints = endpoints

    def update(self, device):
        '''
        update from other device
        '''
        self.properties.update(device.properties)
        self.endpoints.update(device.endpoints)
        self.properties['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')

    def update_endpoint(self, endpoint, data):
        '''
        update endpoint from dict
        '''
        if endpoint not in self.endpoints:
            self.endpoints[endpoint] = {}
        self.endpoints[endpoint].update(data)
        self.properties['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')

    @property
    def addr(self):
        return self.properties['addr']

    @staticmethod
    def from_json(data):
        d = Device()
        d.properties = data.get('properties', {})
        for endpoint in data.get('endpoints', []):
            d.endpoints[endpoint['endpoint']] = endpoint
        return d

    def to_json(self):
        return {'addr': self.addr,
                'properties': self.properties,
                'endpoints': list(self.endpoints.values())}

    def set_property(self, property_id, property_data, endpoint=None):
        if endpoint is None:
            self.properties[property_id] = property_data
        else:
            if endpoint not in self.endpoints:
                self.endpoints[endpoint] = {}
            self.endpoints[endpoint][property_id] = property_data

    def __str__(self):
        return 'Device {}'.format(self.addr)

    def __repr__(self):
        return self.__str__()

    def __setitem__(self, key, value):
        self.properties[key] = value

    def __getitem__(self, key):
        return self.properties[key]

    def __delitem__(self, key):
        return self.properties.__delitem__(key)

    def get(self, key, default):
        return self.properties.get(key, default)

    def __contains__(self, key):
        return self.properties.__contains__(key)

    def __len__(self):
        return len(self.properties)

    def __iter__(self):
        return self.properties.__iter__()

    def items(self):
        return self.properties.items()

    def keys(self):
        return self.properties.keys()

    def __getattr__(self, attr):
        return self.properties[attr]
