#! /usr/bin/python3
from binascii import (hexlify, unhexlify)
from time import (sleep, strftime, time)
from collections import OrderedDict
import logging
import json
import os
from zigate.transport import (SerialConnection, WiFiConnection)

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
ZGT_LAST_SEEN = 'last seen'
ZGT_EVENT = 'event'
ZGT_EVENT_PRESENCE = 'presence detected'
ZGT_STATE = 'state'
ZGT_STATE_ON = 'on-press'
ZGT_STATE_OFF = 'off-release'
ZGT_STATE_MULTI = 'multi_{}'

# commands for external use
ZGT_CMD_NEW_DEVICE = 'new_device'
ZGT_CMD_LIST_ENDPOINTS = 'list_endpoints'


class ZiGate(object):

    def __init__(self, port='auto', path='~/.zigate.json',
                 asyncio_loop=None):
        self._buffer = b''
        self._devices = {}
        self._path = path
        self._version = None
        self._external_command = None
        self._port = port
        self.asyncio_loop = asyncio_loop
        self._last_response = {}  # response to last command type
        self._logger = logging.getLogger(self.__module__)

        self.setup_connection()
        self.init()

    def setup_connection(self):
        self.connection = SerialConnection(self, self._port)

    def close(self):
        try:
            self.connection.close()
        except:
            pass
        self.save_state()

    def save_state(self, path=None):
        path = path or self._path
        self._path = os.path.expanduser(path)
        with open(self._path, 'w') as fp:
            json.dump(list(self._devices.values()), fp, cls=DeviceEncoder)

    def load_state(self, path=None):
        path = path or self._path
        self._path = os.path.expanduser(path)
        if os.path.exists(self._path):
            with open(self._path) as fp:
                devices = json.load(fp)
            for data in devices:
                device = Device.from_json(data)
                self._devices[device.addr] = device
            return True
        return False

    def __del__(self):
        self.close()

    def init(self):
        erase = not self.load_state()
        if erase:
            self.erase_persistent()

        self.set_channel(11)

        # set Type COORDINATOR
        self.set_type('coordinator')

        # start network
        self.start_network()

    @staticmethod
    def zigate_encode(data):
        """encode all characters < 0x02 to avoid """
        encoded = []
        for x in data:
            if x < 0x10:
                encoded.append(0x02)
                encoded.append(x ^ 0x10)
            else:
                encoded.append(x)

        return encoded

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
#         self._devices[str_addr][property_id] = property_data

    def set_external_command(self, func):
        '''
        external func, must accept two args
        command_type and option kwargs
        func(command_type, **kwargs)
        '''
        self._external_command = func

    def call_external_command(self, command_type, **kwargs):
        if self._external_command:
            self._external_command(command_type, **kwargs)

    # Must be overridden by connection
    def send_to_transport(self, data):
        self.connection.send(data)

    # Must be called from a thread loop or asyncio event loop
    def read_data(self, data):
        """Read ZiGate output and split messages"""
        self._buffer += data
        endpos = self._buffer.find(b'\x03')
        while endpos != -1:
            startpos = self._buffer.find(b'\x01')
            # stripping starting 0x01 & ending 0x03
            data_to_decode = \
                self.zigate_decode(self._buffer[startpos + 1:endpos])
            self.decode_data(data_to_decode)
            self._logger.debug('  # encoded : {}'.
                          format(hexlify(self._buffer[startpos:endpos + 1])))
            self._logger.debug('  # decoded : 01{}03'.
                          format(' '.join([format(x, '02x')
                                 for x in data_to_decode]).upper()))
            self._logger.debug('  @timestamp : {}'.format(strftime("%H:%M:%S")))
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    # Calls "transport_write" which must be defined
    # in a serial connection or pyserial_asyncio transport
    def send_data(self, cmd, data=""):
        """send data through ZiGate"""
        byte_cmd = bytes.fromhex(cmd)
        byte_data = bytes.fromhex(data)
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
        self._logger.debug('--------------------------------------')
        self._logger.debug('REQUEST      : {} {}'.format(cmd, data))
        self._logger.debug('  # standard : {}'.format(' '.join([format(x, '02x') for x in std_output]).upper()))
        self._logger.debug('  # encoded  : {}'.format(hexlify(encoded_output)))
        self._logger.debug('(timestamp : {})'.format(strftime("%H:%M:%S")))
        self._logger.debug('--------------------------------------')

        self.send_to_transport(encoded_output)
        status = self._wait_response(b'8000')
        if status:
            self._logger.debug('STATUS code to command {}:{}'.format(cmd, status.get('status')))
            return status.get('status')

    @staticmethod
    def decode_struct(struct, msg):
        output = OrderedDict()
        while struct:
            key, elt_type = struct.popitem(last=False)
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
                key, elt_type = struct.popitem(last=False)
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
                key, elt_type = struct.popitem(last=False)
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

    def decode_data(self, data):
        """Interpret responses attributes"""
        msg_data = data[5:]
        msg_type = hexlify(data[0:2])
        msg = msg_data

        self._last_response[msg_type] = None

        # Do different things based on MsgType
        self._logger.debug('--------------------------------------')
        # Device Announce
        if msg_type == b'004d':
            struct = OrderedDict([('short_addr', 16), ('mac_addr', 64),
                                  ('mac_capability', 'rawend')])
            msg = self.decode_struct(struct, msg_data)
            addr = msg['short_addr'].decode()
            self.set_external_command(ZGT_CMD_NEW_DEVICE,
                                      addr=addr)
            self.set_device_property(msg['short_addr'], 'MAC',
                                     msg['mac_addr'].decode())

            self._logger.debug('RESPONSE 004d : Device Announce')
            self._logger.debug('  * From address   : {}'.format(msg['short_addr']))
            self._logger.debug('  * MAC address    : {}'.format(msg['mac_addr']))
            self._logger.debug('  * MAC capability : {}'.
                          format(msg['mac_capability']))

            self.active_endpoint_request(addr)

        # Status
        elif msg_type == b'8000':
            struct = OrderedDict([('status', 'int'), ('sequence', 8),
                                  ('packet_type', 16), ('info', 'rawend')])
            msg = self.decode_struct(struct, msg_data)

            status_text = self.get_status_text(msg['status'])

            self._logger.debug('RESPONSE 8000 : Status')
            self._logger.debug('  * Status              : {}'.format(status_text))
            self._logger.debug('  - Sequence            : {}'.format(msg['sequence']))
            self._logger.debug('  - Response to command : {}'.format(msg['packet_type']))
            if hexlify(msg['info']) != b'00':
                self._logger.debug('  - Additional msg: ', msg['info'])

        # Default Response
        elif msg_type == b'8001':
            struct = OrderedDict([('level', 'int'), ('info', 'rawend')])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8001 : Log Message')
            self._logger.debug('  - Log Level : {}'.format(ZGT_LOG_LEVELS[msg['level']]))
            self._logger.debug('  - Log Info  : {}'.format(msg['info']))

        # Object Clusters list
        elif msg_type == b'8003':
            struct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_list', 16)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8003 : Object Clusters list')
            self._logger.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            self._logger.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            self._logger.debug('  - cluster_list  : {}'.format(msg['cluster_list']))

        # Object attributes list
        elif msg_type == b'8004':
            struct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_id', 16), ('attribute',16)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8004 : Object attributes list')
            self._logger.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            self._logger.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            self._logger.debug('  - Cluster ID  : {}'.format(msg['cluster_id']))
            self._logger.debug('  - Attributes  : {}'.format(msg['attribute']))

        # Object Commands list
        elif msg_type == b'8005':
            struct = OrderedDict([('endpoint', 8), ('profile_id', 16),
                                  ('cluster_id', 16), ('command',8)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8005 : Object Commands list')
            self._logger.debug('  - Endpoint  : {}'.format(msg['endpoint']))
            self._logger.debug('  - Profile ID  : {}'.format(msg['profile_id']))
            self._logger.debug('  - Cluster ID  : {}'.format(msg['cluster_id']))
            self._logger.debug('  - Commands  : {}'.format(msg['command']))

        # “Factory New” Restart
        elif msg_type == b'8007':
            struct = OrderedDict([('status', 'int')])
            msg = self.decode_struct(struct, msg_data)
            status_codes = {0:'STARTUP', 2:'NFN_START', 6:'RUNNING'}
            self._logger.debug('RESPONSE 8007 : “Factory New” Restart')
            self._logger.debug('  - Status  : {} - {}'.format(msg['status'],
                                                            status_codes.get(msg['status'],
                                                                             'unknown status')))

        # Version List
        elif msg_type == b'8010':
            struct = OrderedDict([('major', 'int16'), ('installer', 'int16')])
            msg = self.decode_struct(struct, msg_data)
            self._logger.debug('RESPONSE 8010 : Version List')
            self._logger.debug('  - Major version     : {}'.format(msg['major']))
            self._logger.debug('  - Installer version : {}'.format(msg['installer']))

        # permt join status
        elif msg_type == b'8014':
            struct = OrderedDict([('status', 'bool')])
            msg = self.decode_struct(struct, msg_data)
            self._logger.debug('RESPONSE 8014 : Permit join status')
            self._logger.debug('  - Status     : {}'.format(msg['status']))

        # device list
        elif msg_type == b'8015':
            struct = OrderedDict([('status', 'bool')])
            msg = self.decode_struct(struct, msg_data)
            self._logger.debug('RESPONSE 8015 : Device list')
            self._logger.debug('  - Status     : {}'.format(msg['status']))

        # Network joined / formed
        elif msg_type == b'8024':
            struct = OrderedDict([('status', 8), ('short_addr', 16), 
                                  ('mac_addr', 64), ('channel', 'int')])
            msg = self.decode_struct(struct, msg_data)
            self._logger.debug('RESPONSE 8024 : Network joined / formed')
            self._logger.debug('  - Status     : {}'.format(msg['status']))
            self._logger.debug('  - Short address   : {}'.format(msg['short_addr']))
            self._logger.debug('  - MAC address    : {}'.format(msg['mac_addr']))
            self._logger.debug('  - Channel    : {}'.format(msg['channel']))

        # Node Descriptor
        elif msg_type == b'8042':
            struct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('manufacturer_code', 16),
                                  ('max_rx', 16), ('max_tx', 16),
                                  ('server_mask', 16),
                                  ('descriptor_capability', 8),
                                  ('mac_flags', 8), ('max_buffer_size', 16),
                                  ('bit_field', 16)])
            msg = self.decode_struct(struct, msg_data)

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

            self._logger.debug('RESPONSE 8042 : Node Descriptor')
            self._logger.debug('  - Sequence          : {}'.format(msg['sequence']))
            self._logger.debug('  - Status            : {}'.format(msg['status']))
            self._logger.debug('  - From address      : {}'.format(msg['addr']))
            self._logger.debug('  - Manufacturer code : {}'.format(msg['manufacturer_code']))
            self._logger.debug('  - Max Rx size       : {}'.format(msg['max_rx']))
            self._logger.debug('  - Max Tx size       : {}'.format(msg['max_tx']))
            self._logger.debug('  - Server mask       : {}'.format(msg['server_mask']))
            self._logger.debug('    - Binary          : {}'.format(server_mask_binary))
            for i, description in enumerate(server_mask_desc, 1):
                self._logger.debug('    - %s : %s' % (description, 'Yes' if server_mask_binary[-i] == '1' else 'No'))
            self._logger.debug('  - Descriptor        : {}'.format(msg['descriptor_capability']))
            self._logger.debug('    - Binary          : {}'.format(descriptor_capability_binary))
            for i, description in enumerate(descriptor_capability_desc, 1):
                self._logger.debug('    - %s : %s' %
                              (description, 'Yes' if descriptor_capability_binary[-i] == '1' else 'No'))
            self._logger.debug('  - Mac flags         : {}'.format(msg['mac_flags']))
            self._logger.debug('    - Binary          : {}'.format(mac_flags_binary))
            for i, description in enumerate(mac_capability_desc, 1):
                self._logger.debug('    - %s : %s' % (description, 'Yes'if mac_flags_binary[-i] == '1' else 'No'))
            self._logger.debug('  - Max buffer size   : {}'.format(msg['max_buffer_size']))
            self._logger.debug('  - Bit field         : {}'.format(msg['bit_field']))
            self._logger.debug('    - Binary          : {}'.format(bit_field_binary))
            for i, description in enumerate(bit_field_desc, 1):
                self._logger.debug('    - %s : %s' % (description, 'Yes' if bit_field_binary[-i] == '1' else 'No'))

        # Cluster List
        elif msg_type == b'8043':
            struct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('length', 8), ('endpoint', 8),
                                  ('profile', 16), ('device_id', 16),
                                  ('bit', 8), ('in_cluster_count', 'count'),
                                  ('in_cluster_list', 16),
                                  ('out_cluster_count', 'count'),
                                  ('out_cluster_list', 16)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8043 : Cluster List')
            self._logger.debug('  - Sequence          : {}'.format(msg['sequence']))
            self._logger.debug('  - Status            : {}'.format(msg['status']))
            self._logger.debug('  - From address      : {}'.format(msg['addr']))
            self._logger.debug('  - Length            : {}'.format(msg['length']))
            self._logger.debug('  - EndPoint          : {}'.format(msg['endpoint']))
            self._logger.debug('  - Profile ID        : {}'.format(msg['profile']))
            self._logger.debug('  - Device ID         : {}'.format(msg['device_id']))
            self._logger.debug('  - IN cluster count  : {}'.format(msg['in_cluster_count']))
            for i, cluster_id in enumerate(msg['in_cluster_list']):
                self._logger.debug('    - Cluster %s : %s (%s)' % (i, cluster_id, CLUSTERS.get(cluster_id, 'unknown')))
            self._logger.debug('  - OUT cluster count  : {}'.format(msg['out_cluster_count']))
            for i, cluster_id in enumerate(msg['out_cluster_list']):
                self._logger.debug('    - Cluster %s : %s (%s)' % (i, cluster_id, CLUSTERS.get(cluster_id, 'unknown')))

        # Power Descriptor
        elif msg_type == b'8044':
            struct = OrderedDict([('sequence', 8), ('status', 8),
                                 ('bit_field', 16), ])
            msg = self.decode_struct(struct, msg_data)

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

            self._logger.debug('RESPONSE 8044 : Power Descriptor')
            self._logger.debug('  - Sequence          : {}'.format(msg['sequence']))
            self._logger.debug('  - Status            : {}'.format(msg['status']))
            self._logger.debug('  - Bit field         : {}'.format(msg['bit_field']))
            self._logger.debug('    - Binary          : {}'.format(bit_field_binary))
            self._logger.debug('    - Current mode    : {}'.format(
                power_mode_desc.get(bit_field_binary[-4:], 'Unknown')))
            self._logger.debug('    - Sources         : ')
            for i, description in enumerate(power_sources, 1):
                self._logger.debug('       - %s : %s %s' %
                              (description,
                               'Yes' if bit_field_binary[8:12][-i] == '1' else 'No',
                               '[CURRENT]' if bit_field_binary[4:8][-i] == '1'else '')
                              )
            self._logger.debug('    - Level           : {}'.format(
                current_power_level.get(bit_field_binary[:4], 'Unknown')))

        # Endpoint List
        elif msg_type == b'8045':
            struct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('endpoint_count', 'count'),
                                  ('endpoint_list', 8)])
            msg = self.decode_struct(struct, msg_data)
            endpoints = [elt.decode() for elt in msg['endpoint_list']]
            self.set_device_property(msg['addr'], 'endpoints', endpoints)
            self.set_external_command(ZGT_CMD_LIST_ENDPOINTS, addr=msg['addr'].decode(), endpoints=endpoints)

            self._logger.debug('RESPONSE 8045 : Active Endpoints List')
            self._logger.debug('  - Sequence       : {}'.format(msg['sequence']))
            self._logger.debug('  - Status         : {}'.format(msg['status']))
            self._logger.debug('  - From address   : {}'.format(msg['addr']))
            self._logger.debug('  - EndPoint count : {}'.
                          format(msg['endpoint_count']))
            for i, endpoint in enumerate(msg['endpoint_list']):
                self._logger.debug('    * EndPoint %s : %s' % (i, endpoint))

        # Leave indication
        elif msg_type == b'8048':
            struct = OrderedDict([('extended_addr', 64), ('rejoin_status', 8)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8048 : Leave indication')
            self._logger.debug('  - From address   : {}'.format(msg['extended_addr']))
            self._logger.debug('  - Rejoin status  : {}'.format(msg['rejoin_status']))

        # Default Response
        elif msg_type == b'8101':
            struct = OrderedDict([('sequence', 8), ('endpoint', 8),
                                 ('cluster', 16), ('command_id', 8),
                                 ('status', 8)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8101 : Default Response')
            self._logger.debug('  - Sequence       : {}'.format(msg['sequence']))
            self._logger.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            self._logger.debug('  - Cluster id     : {} ({})'.format(
                msg['cluster'], CLUSTERS.get(msg['cluster'], 'unknown')))
            self._logger.debug('  - Command        : {}'.format(msg['command_id']))
            self._logger.debug('  - Status         : {}'.format(msg['status']))

        # Read attribute response, Attribute report, Write attribute response
        # Currently only support Xiaomi sensors.
        # Other brands might calc things differently
        elif msg_type in (b'8100', b'8102', b'8110'):
            self._logger.debug('RESPONSE %s : Attribute Report / Response' % msg_type.decode())
            self.interpret_attributes(msg_data)

        # Zone status change
        elif msg_type == b'8401':
            struct = OrderedDict([('sequence', 8), ('endpoint', 8),
                                 ('cluster', 16), ('src_address_mode', 8),
                                 ('src_address', 16), ('zone_status', 16),
                                 ('extended_status', 16), ('zone_id', 8),
                                 ('delay_count', 'count'), ('delay_list', 16)])
            msg = self.decode_struct(struct, msg_data)

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

            self._logger.debug('RESPONSE 8401 : Zone status change notification')
            self._logger.debug('  - Sequence       : {}'.format(msg['sequence']))
            self._logger.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            self._logger.debug('  - Cluster id     : {} ({})'.format(
                msg['cluster'], CLUSTERS.get(msg['cluster'], 'unknown')))
            self._logger.debug('  - Src addr mode  : {}'.format(msg['src_address_mode']))
            self._logger.debug('  - Src address    : {}'.format(msg['src_address']))
            self._logger.debug('  - Zone status    : {}'.format(msg['zone_status']))
            self._logger.debug('    - Binary       : {}'.format(zone_status_binary))
            for i, description in enumerate(zone_status_descs, 1):
                j = int(zone_status_binary[-i])
                self._logger.debug('    - %s : %s' % (description, zone_status_values[i-1][j]))
            self._logger.debug('  - Zone id        : {}'.format(msg['zone_id']))
            self._logger.debug('  - Delay count    : {}'.format(msg['delay_count']))
            for i, value in enumerate(msg['delay_list']):
                self._logger.debug('    - %s : %s' % (i, value))

        # Route Discovery Confirmation
        elif msg_type == b'8701':
            self._logger.debug('RESPONSE 8701: Route Discovery Confirmation')
            self._logger.debug('  - Sequence       : {}'.format(hexlify(msg_data[:1])))
            self._logger.debug('  - Status         : {}'.format(hexlify(msg_data[1:2])))
            self._logger.debug('  - Network status : {}'.format(hexlify(msg_data[2:3])))
            self._logger.debug('  - Message data   : {}'.format(hexlify(msg_data)))

        # APS Data Confirm Fail
        elif msg_type == b'8702':
            struct = OrderedDict([('status', 8), ('src_endpoint', 8),
                                 ('dst_endpoint', 8), ('dst_address_mode', 8),
                                  ('dst_address', 64), ('sequence', 8)])
            msg = self.decode_struct(struct, msg_data)

            self._logger.debug('RESPONSE 8702 : APS Data Confirm Fail')
            self._logger.debug('  - Status         : {}'.format(msg['status']))
            self._logger.debug('  - Src endpoint   : {}'.format(msg['src_endpoint']))
            self._logger.debug('  - Dst endpoint   : {}'.format(msg['dst_endpoint']))
            self._logger.debug('  - Dst mode       : {}'.format(msg['dst_address_mode']))
            self._logger.debug('  - Dst address    : {}'.format(msg['dst_address']))
            self._logger.debug('  - Sequence       : {}'.format(msg['sequence']))

        # No handling for this type of message
        else:
            self._logger.debug('RESPONSE %s : Unknown Message' % msg_type.decode())
            self._logger.debug('  - After decoding  : {}'.format(hexlify(data)))
            self._logger.debug('  - MsgType         : {}'.format(msg_type))
            self._logger.debug('  - MsgLength       : {}'.format(hexlify(data[2:4])))
            self._logger.debug('  - ChkSum          : {}'.format(hexlify(data[4:5])))
            self._logger.debug('  - Data            : {}'.format(hexlify(msg_data)))
            self._logger.debug('  - RSSI            : {}'.format(hexlify(data[-1:])))

        self._last_response[msg_type] = msg

    def interpret_attributes(self, msg_data):
        struct = OrderedDict([('sequence', 8),
                              ('short_addr', 16),
                              ('endpoint', 8),
                              ('cluster_id', 16),
                              ('attribute_id', 16),
                              ('attribute_status', 8),
                              ('attribute_type', 8),
                              ('attribute_size', 'len16'),
                              ('attribute_data', 'raw'),
                              ('end', 'rawend')])
        msg = self.decode_struct(struct, msg_data)
        device_addr = msg['short_addr']
        endpoint = msg['endpoint']
        cluster_id = msg['cluster_id']
        attribute_id = msg['attribute_id']
        attribute_size = msg['attribute_size']
        attribute_data = msg['attribute_data']
        self.set_device_property(device_addr, ZGT_LAST_SEEN,
                                 strftime('%Y-%m-%d %H:%M:%S'))

        if msg['sequence'] == b'00':
            self._logger.debug('  - Sensor type announce (Start after pairing 1)')
        elif msg['sequence'] == b'01':
            self._logger.debug('  - Something announce (Start after pairing 2)')

        # Device type
        if cluster_id == b'0000':
            if attribute_id == b'0005':
                self.set_device_property(device_addr, 'type',
                                         attribute_data.decode(), endpoint)
                self._logger.info(' * type : {}'.format(attribute_data))
            ## proprietary Xiaomi info including battery
            if attribute_id == b'ff01' and attribute_data != b'':
                struct = OrderedDict([('start', 16), ('battery', 16), ('end', 'rawend')])
                raw_info = unhexlify(self.decode_struct(struct, attribute_data)['battery'])
                battery_info = int(hexlify(raw_info[::-1]), 16)/1000
                self.set_device_property(device_addr, endpoint, 'battery', battery_info)
                self._logger.info('  * Battery info')
                self._logger.info('  * Value : {} V'.format(battery_info))
        # Button status
        elif cluster_id == b'0006':
            self._logger.info('  * General: On/Off')
            if attribute_id == b'0000':
                if hexlify(attribute_data) == b'00':
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_ON, endpoint)
                    self._logger.info('  * Closed/Taken off/Press')
                else:
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_OFF, endpoint)
                    self._logger.info('  * Open/Release button')
            elif attribute_id == b'8000':
                clicks = int(hexlify(attribute_data), 16)
                self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_MULTI.format(clicks),
                                             endpoint)
                self._logger.info('  * Multi click')
                self._logger.info('  * Pressed: {} times'.format(clicks))
        # Movement
        elif cluster_id == b'000c':  # Unknown cluster id
            self._logger.info('  * Rotation horizontal')
        elif cluster_id == b'0012':  # Unknown cluster id
            if attribute_id == b'0055':
                if hexlify(attribute_data) == b'0000':
                    self._logger.info('  * Shaking')
                elif hexlify(attribute_data) == b'0055':
                    self._logger.info('  * Rotating vertical')
                    self._logger.info('  * Rotated: {}°'.
                                 format(int(hexlify(attribute_data), 16)))
                elif hexlify(attribute_data) == b'0103':
                    self._logger.info('  * Sliding')
        # Temperature
        elif cluster_id == b'0402':
            temperature = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_TEMPERATURE, temperature, endpoint)
            self._logger.info('  * Measurement: Temperature'),
            self._logger.info('  * Value: {} °C'.format(temperature))
        # Atmospheric Pressure
        elif cluster_id == b'0403':
            self._logger.info('  * Atmospheric pressure')
            pressure = int(hexlify(attribute_data), 16)
            if attribute_id == b'0000':
                self.set_device_property(device_addr, ZGT_PRESSURE, pressure, endpoint)
                self._logger.info('  * Value: {} mb'.format(pressure))
            elif attribute_id == b'0010':
                self.set_device_property(device_addr,
                                         ZGT_DETAILED_PRESSURE, pressure/10, endpoint)
                self._logger.info('  * Value: {} mb'.format(pressure/10))
            elif attribute_id == b'0014':
                self._logger.info('  * Value unknown')
        # Humidity
        elif cluster_id == b'0405':
            humidity = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_HUMIDITY, humidity, endpoint)
            self._logger.info('  * Measurement: Humidity')
            self._logger.info('  * Value: {} %'.format(humidity))
        # Presence Detection
        elif cluster_id == b'0406':
            # Only sent when movement is detected
            if hexlify(attribute_data) == b'01':
                self.set_device_property(device_addr, ZGT_EVENT,
                                         ZGT_EVENT_PRESENCE, endpoint)
                self._logger.debug('   * Presence detection')

        self._logger.info('  FROM ADDRESS      : {}'.format(msg['short_addr']))
        self._logger.debug('  - Source EndPoint : {}'.format(msg['endpoint']))
        self._logger.debug('  - Cluster ID      : {}'.format(msg['cluster_id']))
        self._logger.debug('  - Attribute ID    : {}'.format(msg['attribute_id']))
        self._logger.debug('  - Attribute type  : {}'.format(msg['attribute_type']))
        self._logger.debug('  - Attribute size  : {}'.format(msg['attribute_size']))
        self._logger.debug('  - Attribute data  : {}'.format(
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
        self.send_data('0100', cmd)

    def read_multiple_attributes(self, device_address, device_endpoint, cluster_id, first_attribute_id, attributes):
        """
        Constructs read_attribute command with multiple attributes and sends it

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
        self.send_data('0100', cmd)

    def get_status_text(self, status_code):
        return STATUS_CODES.get(status_code,
                                'Failed with event code: {}'.format(status_code))

    def _wait_response(self, msg_type):
        '''
        wait for next msg_type response
        '''
        t1 = time()
        while self._last_response.get(msg_type) is None:
            sleep(0.1)
            t2 = time()
            if t2-t1 > 3: #no response timeout
                self._logger.error('No response waiting command {}'.format(msg_type))
                raise Exception('No response waiting command {}'.format(msg_type))
        return self._last_response.get(msg_type) 

    def list_devices(self):
        self._logger.debug('-- DEVICE REPORT -------------------------')
        for addr in self._devices.keys():
            self._logger.info('- addr : {}'.format(addr))
            for k, v in self._devices[addr].items():
                self._logger.info('    * {} : {}'.format(k, v))
        self._logger.debug('-- DEVICE REPORT - END -------------------')
        return self._devices

    def get_devices_list(self):
        self.send_data('0015')
        self._wait_response(b'8015')

    def get_version(self):
        if not self._version:
            self.send_data('0010')
            self._version = self._wait_response(b'8010')
        return self._version

    def get_version_text(self):
        return '{0[major]}.{0[installer]}'.format(self.get_version())

    def reset(self):
        return self.send_data('0011')

    def erase_persistent(self):
        return self.send_data('0012')
        # todo, erase local persitent

    def is_permitting_join(self):
        self.send_data('0014')
        r = self._wait_response(b'8014')
        if r:
            r = r.get('status', False)
        return r

    def permit_join(self, duration=30):
        """permit join for 30 secs (1E)"""
        return self.send_data("0049", 'FFFC{:02X}00'.format(duration))

    def set_channel(self, channel):
        return self.send_data('0021', '00000800') #channel 11

    def set_type(self, typ='coordinator'):
        TYP = {'coordinator': '00',
               'router': '01',
               'legacy router': '02'}
        self.send_data('0023', TYP[typ])

    def start_network(self):
        return self.send_data('0024')
#         return self._wait_response(b'8024')

    def start_network_scan(self):
        return self.send_data('0025')

    def remove_device(self, addr):
        return self.send_data('0026', addr)

    def simple_descriptor_request(self, addr, endpoint):
        return self.send_data('0043', addr+endpoint)

    def active_endpoint_request(self, addr):
        return self.send_data('0045', addr)


class ZiGateWiFi(ZiGate):
    def __init__(self, host, port, path='~/.zigate.json', 
                 asyncio_loop=None):
        self._host = host
        ZiGate.__init__(self, port=port, path=path, asyncio_loop=asyncio_loop)

    def setup_connection(self):
        self.connection = WiFiConnection(self, self._host, self._port)


class DeviceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Device):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)


class Device(object):
    def __init__(self, addr):
        self.addr = addr
        self.endpoints = {}
        self.properties = {}

    @staticmethod
    def from_json(data):
        d = Device(data['addr'])
        d.properties = data.get('properties', {})
        d.endpoints = data.get('endpoints', {})
        return d

    def to_json(self):
        return {'addr': self.addr, 
                'properties': self.properties,
                'endpoints': self.endpoints}

    def set_property(self, property_id, property_data, endpoint=None):
        if endpoint is None:
            self.properties[property_id] = property_data
        else:
            if endpoint not in self.endpoints:
                self.endpoints[endpoint] = {}
            self.endpoints[endpoint][property_id] = property_data

    def __str__(self, *args, **kwargs):
        return 'Device {}'.format(self.addr)

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


