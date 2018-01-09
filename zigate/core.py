#! /usr/bin/python3
from binascii import (hexlify, unhexlify)
from time import (sleep, strftime)
from collections import OrderedDict
import logging
import json
import os

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

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

# states & properties
ZGT_TEMPERATURE = 'temperature'
ZGT_PRESSURE = 'pressure'
ZGT_DETAILED_PRESSURE = 'detailed pressure'
ZGT_HUMIDITY = 'humidity'
ZGT_LAST_SEEN = 'last seen'
ZGT_EVENT = 'event'
ZGT_EVENT_PRESENCE = 'presence detected'
ZGT_STATE = 'state'
ZGT_STATE_OPEN = 'open'
ZGT_STATE_CLOSED = 'closed'


# commands for external use
ZGT_CMD_NEW_DEVICE = 'new device'

class ZiGate():

    def __init__(self,port='/dev/ttyUSB0',method='thread',path='~/.zigate.json'):
        self._buffer = b''
        self._devices = {}
        self._path = path
        if method == 'thread':
            self.connection = Threaded_connection(self,port)
        elif method == 'async':
            self.connection = Async_connection(self,port)
        elif method == 'fake':
            self.connection = Fake_connection(self,port)
        elif method == 'tcp':
            self.connection = TCP_connection(self,port)
        else:
            raise Exception('Unknown connection method')
        erase = self.load_state()
        self.init(erase)
      
    def close(self):
        self.connection.close()
        self.save_state()
        
    def save_state(self, path=None):
        path = path or self._path
        self._path = os.path.expanduser(path)
        with open(self._path,'w') as fp:
            json.dump(list(self._devices.values()),fp,cls=DeviceEncoder)
    
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
        
    def init(self, erase=False):
        if erase:
            self.send_data('0012')
            
        # set channel 11
        self.send_data('0021', '00000800')

        # set Type COORDINATOR
        self.send_data('0023','00')
        
        # start network
        self.send_data('0024')
    
        # start inclusion mode 30sec
        self.permit_join()
#         self.send_data('0049','FFFC1E00')

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
    def set_device_property(self, addr, property_id, property_data):
        """
        log property / attribute value in a device based dictionnary
        please note that short addr is not stable if device is reset
        (still have to find the unique ID)
        all data stored must be directly usable (i.e no bytes)
        """
        str_addr = addr.decode()
        if str_addr not in self._devices:
            self._devices[str_addr] = Device(str_addr)
        self._devices[str_addr][property_id] = property_data

    # Must be overridden by external program
    def set_external_command(self, command_type, **kwargs):
        pass

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
            self.interpret_data(data_to_decode)
            _LOGGER.debug('  # encoded : {}'.
                          format(hexlify(self._buffer[startpos:endpos + 1])))
            _LOGGER.debug('  # decoded : 01{}03'.
                          format(' '.join([format(x, '02x')
                                 for x in data_to_decode]).upper()))
            _LOGGER.debug('  (@timestamp : {}'.format(strftime("%H:%M:%S")))
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
        _LOGGER.debug('--------------------------------------')
        _LOGGER.debug('REQUEST      : {} {}'.format(cmd, data))
        _LOGGER.debug('  # standard : {}'.
                      format(' '.join([format(x, '02x')
                             for x in std_output]).upper()))
        _LOGGER.debug('  # encoded  : {}'.format(hexlify(encoded_output)))
        _LOGGER.debug('(timestamp : {})'.format(strftime("%H:%M:%S")))
        _LOGGER.debug('--------------------------------------')

        self.send_to_transport(encoded_output)

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

    def interpret_data(self, data):
        """Interpret responses attributes"""
        msg_data = data[5:]
        msg_type = hexlify(data[0:2])

        # Do different things based on MsgType
        _LOGGER.debug('--------------------------------------')
        # Device Announce
        if msg_type == b'004d':
            struct = OrderedDict([('short_addr', 16), ('mac_addr', 64),
                                  ('mac_capability', 'rawend')])
            msg = self.decode_struct(struct, msg_data)

            self.set_external_command(ZGT_CMD_NEW_DEVICE,
                                      addr=msg['short_addr'].decode())
            self.set_device_property(msg['short_addr'], 'MAC',
                                     msg['mac_addr'].decode())

            _LOGGER.debug('RESPONSE 004d : Device Announce')
            _LOGGER.debug('  * From address   : {}'.format(msg['short_addr']))
            _LOGGER.debug('  * MAC address    : {}'.format(msg['mac_addr']))
            _LOGGER.debug('  * MAC capability : {}'.
                          format(msg['mac_capability']))

        # Status
        elif msg_type == b'8000':
            struct = OrderedDict([('status', 'int'), ('sequence', 8),
                                  ('packet_type', 16), ('info', 'rawend')])
            msg = self.decode_struct(struct, msg_data)

            status_codes = {0: 'Success', 1: 'Invalid parameters',
                            2: 'Unhandled command', 3: 'Command failed',
                            4: 'Busy', 5: 'Stack already started'}
            status_text = status_codes.get(msg['status'],
                                           'Failed with event code: %i' %
                                           msg['status'])

            _LOGGER.debug('RESPONSE 8000 : Status')
            _LOGGER.debug('  * Status              : {}'.format(status_text))
            _LOGGER.debug('  - Sequence            : {}'.
                          format(msg['sequence']))
            _LOGGER.debug('  - Response to command : {}'.
                          format(msg['packet_type']))
            if hexlify(msg['info']) != b'00':
                _LOGGER.debug('  - Additional msg: ', msg['info'])

        # Default Response
        elif msg_type == b'8001':
            ZGT_LOG_LEVELS = ['Emergency', 'Alert', 'Critical', 'Error',
                              'Warning', 'Notice', 'Information', 'Debug']
            struct = OrderedDict([('level', 'int'), ('info', 'rawend')])
            msg = self.decode_struct(struct, msg_data)

            _LOGGER.debug('RESPONSE 8001 : Log Message')
            _LOGGER.debug('  - Log Level : {}'.
                          format(ZGT_LOG_LEVELS[msg['level']]))
            _LOGGER.debug('  - Log Info  : {}'.format(msg['info']))

        # Version List
        elif msg_type == b'8010':
            struct = OrderedDict([('major', 'int16'), ('installer', 'int16')])
            msg = self.decode_struct(struct, msg_data)

            _LOGGER.debug('RESPONSE : Version List')
            _LOGGER.debug('  - Major version     : {}'.format(msg['major']))
            _LOGGER.debug('  - Installer version : {}'.
                          format(msg['installer']))

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
            descriptor_capability_binary = \
                format(int(msg['descriptor_capability'], 16), '08b')
            mac_flags_binary = format(int(msg['mac_flags'], 16), '08b')
            bit_field_binary = format(int(msg['bit_field'], 16), '016b')

            # Length 16, 7-15 Reserved
            server_mask_description = ['Primary trust center',
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

            _LOGGER.debug('RESPONSE 8042 : Node Descriptor')
            _LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            _LOGGER.debug('  - Status            : {}'.format(msg['status']))
            _LOGGER.debug('  - From address      : {}'.format(msg['addr']))
            _LOGGER.debug('  - Manufacturer code : {}'.
                          format(msg['manufacturer_code']))
            _LOGGER.debug('  - Max Rx size       : {}'.format(msg['max_rx']))
            _LOGGER.debug('  - Max Tx size       : {}'.format(msg['max_tx']))
            _LOGGER.debug('  - Server mask       : {}'.
                          format(msg['server_mask']))
            _LOGGER.debug('    - Binary          : {}'.
                          format(server_mask_binary))
            for i, description in enumerate(server_mask_desc, 1):
                _LOGGER.debug('    - %s : %s' %
                              (description,
                               'Yes' if server_mask_binary[-i] == '1'
                               else 'No'))
            _LOGGER.debug('  - Descriptor        : {}'.
                          format(msg['descriptor_capability']))
            _LOGGER.debug('    - Binary          : {}'.
                          format(descriptor_capability_binary))
            for i, description in enumerate(descriptor_capability_desc, 1):
                _LOGGER.debug('    - %s : %s' %
                              (description,
                               'Yes' if descriptor_capability_binary[-i] == '1'
                               else 'No'))
            _LOGGER.debug('  - Mac flags         : {}'.
                          format(msg['mac_flags']))
            _LOGGER.debug('    - Binary          : {}'.
                          format(mmac_flags_binary))
            for i, description in enumerate(mac_capability_desc, 1):
                _LOGGER.debug('    - %s : %s' %
                              (description,
                               'Yes'if mac_flags_binary[-i] == '1'
                               else 'No'))
            _LOGGER.debug('  - Max buffer size   : {}'.
                          format(msg['max_buffer_size']))
            _LOGGER.debug('  - Bit field         : {}'.
                          format(msg['bit_field']))
            _LOGGER.debug('    - Binary          : {}'.
                          format(bit_field_binary))
            for i, description in enumerate(bit_field_desc, 1):
                _LOGGER.debug('    - %s : %s' %
                              (description,
                               'Yes' if bit_field_binary[-i] == '1'
                               else 'No'))

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

            _LOGGER.debug('RESPONSE 8043 : Cluster List')
            _LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            _LOGGER.debug('  - Status            : {}'.format(msg['status']))
            _LOGGER.debug('  - From address      : {}'.format(msg['addr']))
            _LOGGER.debug('  - Length            : {}'.format(msg['length']))
            _LOGGER.debug('  - EndPoint          : {}'.format(msg['endpoint']))
            _LOGGER.debug('  - Profile ID        : {}'.format(msg['profile']))
            _LOGGER.debug('  - Device ID         : {}'.
                          format(msg['device_id']))
            _LOGGER.debug('  - IN cluster count  : {}'.
                          format(msg['in_cluster_count']))
            for i, cluster_id in enumerate(msg['in_cluster_list']):
                _LOGGER.debug('    - Cluster %s : %s (%s)' %
                              (i, cluster_id,
                               CLUSTERS.get(cluster_id, 'unknown')))
            _LOGGER.debug('  - OUT cluster count  : {}'.
                          format(msg['out_cluster_count']))
            for i, cluster_id in enumerate(msg['out_cluster_list']):
                _LOGGER.debug('    - Cluster %s : %s (%s)' %
                              (i, cluster_id,
                               CLUSTERS.get(cluster_id, 'unknown')))

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

            _LOGGER.debug('RESPONSE 8044 : Power Descriptor')
            _LOGGER.debug('  - Sequence          : {}'.format(msg['sequence']))
            _LOGGER.debug('  - Status            : {}'.format(msg['status']))
            _LOGGER.debug('  - Bit field         : {}'.
                          format(msg['bit_field']))
            _LOGGER.debug('    - Binary          : {}'.
                          format(bit_field_binary))
            _LOGGER.debug('    - Current mode    : {}'.
                          format(power_mode_desc.
                                 get(bit_field_binary[-4:], 'Unknown')))
            _LOGGER.debug('    - Sources         : ')
            for i, description in enumerate(power_sources, 1):
                _LOGGER.debug('       - %s : %s %s' %
                              (description,
                               'Yes' if bit_field_binary[8:12][-i] == '1'
                               else 'No',
                               '[CURRENT]' if bit_field_binary[4:8][-i] == '1'
                               else ''))
            _LOGGER.debug('    - Level           : {}'.
                          format(current_power_level.get(bit_field_binary[:4],
                                                         'Unknown')))

        # Endpoint List
        elif msg_type == b'8045':
            struct = OrderedDict([('sequence', 8), ('status', 8), ('addr', 16),
                                  ('endpoint_count', 'count'),
                                  ('endpoint_list', 8)])
            msg = self.decode_struct(struct, msg_data)
            endpoints = [elt.decode() for elt in msg['endpoint_list']]
            self.set_device_property(msg['addr'], 'endpoints', endpoints)

            _LOGGER.debug('RESPONSE 8045 : Active Endpoints List')
            _LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            _LOGGER.debug('  - Status         : {}'.format(msg['status']))
            _LOGGER.debug('  - From address   : {}'.format(msg['addr']))
            _LOGGER.debug('  - EndPoint count : {}'.
                          format(msg['endpoint_count']))
            for i, endpoint in enumerate(msg['endpoint_list']):
                _LOGGER.debug('    * EndPoint %s : %s' % (i, endpoint))

        # Leave indication
        elif msg_type == b'8048':
            struct = OrderedDict([('extended_addr', 64), ('rejoin_status', 8)])
            msg = self.decode_struct(struct, msg_data)

            _LOGGER.debug('RESPONSE 8048 : Leave indication')
            _LOGGER.debug('  - From address   : {}'.
                          format(msg['extended_addr']))
            _LOGGER.debug('  - Rejoin status  : {}'.
                          format(msg['rejoin_status']))

        # Default Response
        elif msg_type == b'8101':
            struct = OrderedDict([('sequence', 8), ('endpoint', 8),
                                 ('cluster', 16), ('command_id', 8),
                                 ('status', 8)])
            msg = self.decode_struct(struct, msg_data)

            _LOGGER.debug('RESPONSE 8101 : Default Response')
            _LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            _LOGGER.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            _LOGGER.debug('  - Cluster id     :  %s (%s)' %
                          (msg['cluster'], CLUSTERS.get(msg['cluster'],
                           'unknown')))
            _LOGGER.debug('  - Command        : {}'.format(msg['command_id']))
            _LOGGER.debug('  - Status         : {}'.format(msg['status']))

        # Read attribute response, Attribute report, Write attribute response
        # Currently only support Xiaomi sensors.
        # Other brands might calc things differently
        elif msg_type in (b'8100', b'8102', b'8110'):
            _LOGGER.debug('RESPONSE %s : Attribute Report / Response' %
                          msg_type.decode())
            self.interpret_attribute(msg_data)

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

            _LOGGER.debug('RESPONSE 8401 : Zone status change notification')
            _LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))
            _LOGGER.debug('  - EndPoint       : {}'.format(msg['endpoint']))
            _LOGGER.debug('  - Cluster id     :  %s (%s)' %
                          (msg['cluster'], CLUSTERS.get(msg['cluster'],
                           'unknown')))
            _LOGGER.debug('  - Src addr mode  : {}'.format(
                          msg['src_address_mode']))
            _LOGGER.debug('  - Src address    : {}'.format(msg['src_address']))
            _LOGGER.debug('  - Zone status    : {}'.format(msg['zone_status']))
            _LOGGER.debug('    - Binary       : {}'.format(zone_status_binary))
            for i, description in enumerate(zone_status_descs, 1):
                j = int(zone_status_binary[-i])
                _LOGGER.debug('    - %s : %s' % (description,
                              zone_status_values[i-1][j]))
            _LOGGER.debug('  - Zone id        : {}'.format(msg['zone_id']))
            _LOGGER.debug('  - Delay count    : {}'.format(msg['delay_count']))
            for i, value in enumerate(msg['delay_list']):
                _LOGGER.debug('    - %s : %s' % (i, value))

        # Route Discovery Confirmation
        elif msg_type == b'8701':
            _LOGGER.debug('RESPONSE 8701: Route Discovery Confirmation')
            _LOGGER.debug('  - Sequence       : {}'.
                          format(hexlify(msg_data[:1])))
            _LOGGER.debug('  - Status         : {}'.
                          format(hexlify(msg_data[1:2])))
            _LOGGER.debug('  - Network status : {}'.
                          format(hexlify(msg_data[2:3])))
            _LOGGER.debug('  - Message data   : {}'.format(hexlify(msg_data)))

        # APS Data Confirm Fail
        elif msg_type == b'8702':
            struct = OrderedDict([('status', 8), ('src_endpoint', 8),
                                 ('dst_endpoint', 8), ('dst_address_mode', 8),
                                  ('dst_address', 64), ('sequence', 8)])
            msg = self.decode_struct(struct, msg_data)

            _LOGGER.debug('RESPONSE 8702 : APS Data Confirm Fail')
            _LOGGER.debug('  - Status         : {}'.format(msg['status']))
            _LOGGER.debug('  - Src endpoint   : {}'.
                          format(msg['src_endpoint']))
            _LOGGER.debug('  - Dst endpoint   : {}'.
                          format(msg['dst_endpoint']))
            _LOGGER.debug('  - Dst mode       : {}'.
                          format(msg['dst_address_mode']))
            _LOGGER.debug('  - Dst address    : {}'.format(msg['dst_address']))
            _LOGGER.debug('  - Sequence       : {}'.format(msg['sequence']))

        # No handling for this type of message
        else:
            _LOGGER.debug('RESPONSE %s : Unknown Message' % msg_type.decode())
            _LOGGER.debug('  - After decoding  : {}'.format(hexlify(data)))
            _LOGGER.debug('  - MsgType         : {}'.format(msg_type))
            _LOGGER.debug('  - MsgLength       : {}'.format(hexlify(data[2:4]))
                          )
            _LOGGER.debug('  - ChkSum          : {}'.format(hexlify(data[4:5]))
                          )
            _LOGGER.debug('  - Data            : {}'.format(hexlify(msg_data))
                          )
            _LOGGER.debug('  - RSSI            : {}'.format(hexlify(data[-1:]))
                          )

    def interpret_attribute(self, msg_data):
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
        cluster_id = msg['cluster_id']
        attribute_id = msg['attribute_id']
        attribute_size = msg['attribute_size']
        attribute_data = msg['attribute_data']
        self.set_device_property(device_addr, ZGT_LAST_SEEN,
                                 strftime('%Y-%m-%d %H:%M:%S'))

        if msg['sequence'] == b'00':
            _LOGGER.debug('  - Sensor type announce (Start after pairing 1)')
        elif msg['sequence'] == b'01':
            _LOGGER.debug('  - Something announce (Start after pairing 2)')

        # Device type
        if cluster_id == b'0000':
            if attribute_id == b'0005':
                self.set_device_property(device_addr, 'type',
                                         attribute_data.decode())
                _LOGGER.info(' * type : {}'.format(attribute_data))
        # Button status
        elif cluster_id == b'0006':
            _LOGGER.info('  * General: On/Off')
            if attribute_id == b'0000':
                if hexlify(attribute_data) == b'00':
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_CLOSED)
                    _LOGGER.info('  * Closed/Taken off/Press')
                else:
                    self.set_device_property(device_addr, ZGT_STATE,
                                             ZGT_STATE_OPEN)
                    _LOGGER.info('  * Open/Release button')
            elif attribute_id == b'8000':
                _LOGGER.info('  * Multi click')
                _LOGGER.info('  * Pressed: ',
                             int(hexlify(attribute_data), 16), ' times')
        # Movement
        elif cluster_id == b'000c':  # Unknown cluster id
            _LOGGER.info('  * Rotation horizontal')
        elif cluster_id == b'0012':  # Unknown cluster id
            if attribute_id == b'0055':
                if hexlify(attribute_data) == b'0000':
                    _LOGGER.info('  * Shaking')
                elif hexlify(attribute_data) == b'0055':
                    _LOGGER.info('  * Rotating vertical')
                    _LOGGER.info('  * Rotated: ',
                                 int(hexlify(attribute_data), 16), '°')
                elif hexlify(attribute_data) == b'0103':
                    _LOGGER.info('  * Sliding')
        # Temperature
        elif cluster_id == b'0402':
            temperature = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_TEMPERATURE, temperature)
            _LOGGER.info('  * Measurement: Temperature'),
            _LOGGER.info('  * Value: {}'.format(temperature, '°C'))
        # Atmospheric Pressure
        elif cluster_id == b'0403':
            _LOGGER.info('  * Atmospheric pressure')
            pressure = int(hexlify(attribute_data), 16)
            if attribute_id == b'0000':
                self.set_device_property(device_addr, ZGT_PRESSURE, pressure)
                _LOGGER.info('  * Value: {}'.format(pressure, 'mb'))
            elif attribute_id == b'0010':
                self.set_device_property(device_addr,
                                         ZGT_DETAILED_PRESSURE, pressure/10)
                _LOGGER.info('  * Value: {}'.format(pressure/10, 'mb'))
            elif attribute_id == b'0014':
                _LOGGER.info('  * Value unknown')
        # Humidity
        elif cluster_id == b'0405':
            humidity = int(hexlify(attribute_data), 16) / 100
            self.set_device_property(device_addr, ZGT_HUMIDITY, humidity)
            _LOGGER.info('  * Measurement: Humidity')
            _LOGGER.info('  * Value: {}'.format(humidity, '%'))
        # Presence Detection
        elif cluster_id == b'0406':
            # Only sent when movement is detected
            if hexlify(attribute_data) == b'01':
                self.set_device_property(device_addr, ZGT_EVENT,
                                         ZGT_EVENT_PRESENCE)
                _LOGGER.debug('   * Presence detection')

        _LOGGER.info('  FROM ADDRESS      : {}'.format(msg['short_addr']))
        _LOGGER.debug('  - Source EndPoint : {}'.format(msg['endpoint']))
        _LOGGER.debug('  - Cluster ID      : {}'.format(msg['cluster_id']))
        _LOGGER.debug('  - Attribute ID    : {}'.format(msg['attribute_id']))
        _LOGGER.debug('  - Attribute type  : {}'.format(msg['attribute_type']))
        _LOGGER.debug('  - Attribute size  : {}'.format(msg['attribute_size']))
        _LOGGER.debug('  - Attribute data  : {}'.format(
                                               hexlify(msg['attribute_data'])))

    def list_devices(self):
        _LOGGER.debug('-- DEVICE REPORT -------------------------')
        for addr in self._devices.keys():
            _LOGGER.info('- addr : {}'.format(addr))
            for k, v in self._devices[addr].items():
                _LOGGER.info('    * {} : {}'.format(k, v))
        _LOGGER.debug('-- DEVICE REPORT - END -------------------')

    def permit_join(self):
        """permit join for 30 secs (1E)"""
        self.send_data("0049", "FFFC1E00")

class DeviceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Device):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)

class Device(object):
    def __init__(self, addr):
        self.addr = addr
        self.properties = {}
        
    @staticmethod
    def from_json(data):
        d = Device(data['addr'])
        d.properties = data.get('properties',{})
        return d
        
    def to_json(self):
        return {'addr':self.addr,'properties':self.properties}
        
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

class Fake_connection(object):
    def __init__(self, device, port=None):
        pass
    
    def close(self):
        pass
    
    def read(self):
        pass
    
    def send(self, data):
        print('Fake send :',data)

# Functions when used with serial & threads
class Threaded_connection(Fake_connection):

    def __init__(self, device, port='/dev/ttyUSB0'):
        import serial
        import threading

        self.device = device
        self.cnx = serial.Serial(port, 115200, timeout=0)
        self.thread = threading.Thread(target=self.read)
        self.thread.setDaemon(True)
        self.thread.start()
        
    def read(self):
        while True:
            bytesavailable = self.cnx.inWaiting()
            if bytesavailable > 0:
                self.device.read_data(self.cnx.read(bytesavailable))

    def send(self, data):
        self.cnx.write(data)
        
class Async_connection(Fake_connection):
    pass
        
class TCP_connection(Fake_connection):
    pass

# import asyncio
# import serial_asyncio
# from functools import partial
#
#
# class Async_connection(object):
#
#     def __init__(self, device, port='/dev/ttyUSB0'):
#         loop = asyncio.get_event_loop()
#         coro = serial_asyncio.create_serial_connection(
#                      loop, SerialProtocol, port, baudrate=115200)
#         futur = asyncio.run_coroutine_threadsafe(coro, loop)
#         futur.add_done_callback(
#                      partial(self.bind_transport_to_device, device))
#         loop.run_forever()
#         loop.close()
#
#     def bind_transport_to_device(self, device, protocol_refs):
#         """
#         Bind device and protocol / transport once they are ready
#         Update the device status @ start
#         """
#         transport = protocol_refs.result()[0]
#         protocol = protocol_refs.result()[1]
#         protocol.device = device
#         device.send_to_transport = transport.write
#
# class SerialProtocol(asyncio.Protocol):
#
#     def connection_made(self, transport):
#         self.transport = transport
#         transport.serial.rts = False
#
#     def data_received(self, data):
#         try:
#             self.device.read_data(data)
#         except:
#             _LOGGER.debug('ERROR')
#
#     def connection_lost(self, exc):
#         pass


if __name__ == "__main__":

    zigate = ZiGate()

    # Thread base connection
#     connection = Threaded_connection(zigate)

    # Asyncio based connection
    # (comment thread elements)
    # (uncomment async imports & classes)
    # connection = Async_connection(zigate)

    zigate.send_data('0010')
    zigate.list_devices()
