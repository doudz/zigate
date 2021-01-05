#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

import struct
import logging
from collections import OrderedDict
from binascii import hexlify
from .const import DATA_TYPE

LOGGER = logging.getLogger('zigate')

RESPONSES = {}


def register_response(o):
    RESPONSES[o.msg] = o
    return o


class Response(object):
    msg = 0x0
    type = 'Base response'
    s = OrderedDict()
    format = {'addr': '{:04x}',
              'ieee': '{:016x}',
              'group': '{:04x}'}

    def __init__(self, msg_data, lqi):
        self.msg_data = msg_data
        self.lqi = lqi
        self.data = OrderedDict()
        self.decode()

    def __str__(self):
        d = ['{}:{}'.format(k, v) for k, v in self.data.items()]
        return 'RESPONSE 0x{:04X} - {} : {}'.format(self.msg,
                                                    self.type,
                                                    ', '.join(d))

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        return self.data.__delitem__(key)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __contains__(self, key):
        return self.data.__contains__(key)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return self.data.__iter__()

    def items(self):
        return self.data.items()

    def keys(self):
        return self.data.keys()

    def __getattr__(self, attr):
        return self.data[attr]

    def decode(self):
        fmt = '!'
        msg_data = self.msg_data
        keys = list(self.s.keys())
        for k, v in self.s.items():
            if isinstance(v, OrderedDict):
                keys.remove(k)
                self.data[k] = []
                rest = len(msg_data) - struct.calcsize(fmt)
                if rest == 0:
                    continue
                subfmt = '!' + ''.join(v.values())
                count = rest // struct.calcsize(subfmt)
                submsg_data = msg_data[-rest:]
                msg_data = msg_data[:-rest]
                for i in range(count):
                    sdata, submsg_data = self._decode(subfmt,
                                                      v.keys(),
                                                      submsg_data)
                    self.data[k].append(sdata)
            elif v == 'rawend':
                fmt += '{}s'.format(len(msg_data) - struct.calcsize(fmt))
            else:
                fmt += v
        sdata, msg_data = self._decode(fmt, keys, msg_data)
        self.data.update(sdata)
        if msg_data:
            self.data['additional'] = msg_data

        # reformat output, TODO: do it live
        self._format(self.data)
        self.data['lqi'] = self.lqi

    def _decode(self, fmt, keys, data):
        size = struct.calcsize(fmt)
        sdata = OrderedDict(zip(keys, struct.unpack(fmt, data[:size])))
        data = data[size:]
        return sdata, data

    def _format(self, data, keys=[]):
        keys = keys or data.keys()
        for k in keys:
            if k in self.format:
                data[k] = self.format[k].format(data[k])
            elif isinstance(data[k], list):
                if data[k] and isinstance(data[k][0], dict):
                    for subdata in data[k]:
                        self._format(subdata)

    def _filter_data(self, include=[], exclude=[]):
        if include:
            return {k: v for k, v in self.data.items() if k in include}
        elif exclude:
            return {k: v for k, v in self.data.items() if k not in exclude}

    def cleaned_data(self):
        ''' return cleaned data
        need to be override in subclass
        '''
        return self.data


@register_response
class R8000(Response):
    msg = 0x8000
    type = 'Status response'
    s = OrderedDict([('status', 'B'),
                    ('sequence', 'B'),
                    ('packet_type', 'H'),
                    ('error', 'rawend')])

    def decode(self):
        Response.decode(self)
#         self.data['packet_type'] = hexlify(self.data['packet_type'])

    def status_text(self):
        status_codes = {0: 'Success',
                        1: 'Incorrect parameters',
                        2: 'Unhandled command',
                        3: 'Command failed',
                        4: ('Busy (Node is carrying out a lengthy operation '
                            'and is currently unable to handle'
                            ' the incoming command)'),
                        5: ('Stack already started'
                            ' (no new configuration accepted)'),
                        }
        ZCL_status_codes = {0: 'E_ZCL_SUCCESS',
                            1: 'E_ZCL_FAIL',
                            2: 'E_ZCL_ERR_PARAMETER_NULL',
                            3: 'E_ZCL_ERR_PARAMETER_RANGE',
                            4: 'E_ZCL_ERR_HEAP_FAIL',
                            5: 'E_ZCL_ERR_EP_RANGE',
                            6: 'E_ZCL_ERR_EP_UNKNOWN',
                            7: 'E_ZCL_ERR_SECURITY_RANGE',
                            8: 'E_ZCL_ERR_CLUSTER_0',
                            9: 'E_ZCL_ERR_CLUSTER_NULL',
                            10: 'E_ZCL_ERR_CLUSTER_NOT_FOUND',
                            11: 'E_ZCL_ERR_CLUSTER_ID_RANGE',
                            12: 'E_ZCL_ERR_ATTRIBUTES_NULL',
                            13: 'E_ZCL_ERR_ATTRIBUTES_0',
                            14: 'E_ZCL_ERR_ATTRIBUTE_WO',
                            15: 'E_ZCL_ERR_ATTRIBUTE_RO',
                            16: 'E_ZCL_ERR_ATTRIBUTES_ACCESS',
                            17: 'E_ZCL_ERR_ATTRIBUTE_TYPE_UNSUPPORTED',
                            18: 'E_ZCL_ERR_ATTRIBUTE_NOT_FOUND',
                            19: 'E_ZCL_ERR_CALLBACK_NULL',
                            20: 'E_ZCL_ERR_ZBUFFER_FAIL',
                            21: 'E_ZCL_ERR_ZTRANSMIT_FAIL',
                            22: 'E_ZCL_ERR_CLIENT_SERVER_STATUS',
                            23: 'E_ZCL_ERR_TIMER_RESOURCE',
                            24: 'E_ZCL_ERR_ATTRIBUTE_IS_CLIENT',
                            25: 'E_ZCL_ERR_ATTRIBUTE_IS_SERVER',
                            26: 'E_ZCL_ERR_ATTRIBUTE_RANGE',
                            27: 'E_ZCL_ERR_ATTRIBUTE_MISMATCH',
                            28: 'E_ZCL_ERR_KEY_ESTABLISHMENT_MORE_THAN_ONE_CLUSTER',
                            29: 'E_ZCL_ERR_INSUFFICIENT_SPACE',
                            30: 'E_ZCL_ERR_NO_REPORTABLE_CHANGE',
                            31: 'E_ZCL_ERR_NO_REPORT_ENTRIES',
                            32: 'E_ZCL_ERR_ATTRIBUTE_NOT_REPORTABLE',
                            33: 'E_ZCL_ERR_ATTRIBUTE_ID_ORDER',
                            34: 'E_ZCL_ERR_MALFORMED_MESSAGE',
                            35: 'E_ZCL_ERR_MANUFACTURER_SPECIFIC',
                            36: 'E_ZCL_ERR_PROFILE_ID',
                            37: 'E_ZCL_ERR_INVALID_VALUE',
                            38: 'E_ZCL_ERR_CERT_NOT_FOUND',
                            39: 'E_ZCL_ERR_CUSTOM_DATA_NULL',
                            40: 'E_ZCL_ERR_TIME_NOT_SYNCHRONISED',
                            41: 'E_ZCL_ERR_SIGNATURE_VERIFY_FAILED',
                            42: 'E_ZCL_ERR_ZRECEIVE_FAIL',
                            43: 'E_ZCL_ERR_KEY_ESTABLISHMENT_END_POINT_NOT_FOUND',
                            44: 'E_ZCL_ERR_KEY_ESTABLISHMENT_CLUSTER_ENTRY_NOT_FOUND',
                            45: 'E_ZCL_ERR_KEY_ESTABLISHMENT_CALLBACK_ERROR',
                            46: 'E_ZCL_ERR_SECURITY_INSUFFICIENT_FOR_CLUSTER',
                            47: 'E_ZCL_ERR_CUSTOM_COMMAND_HANDLER_NULL_OR_RETURNED_ERROR',
                            48: 'E_ZCL_ERR_INVALID_IMAGE_SIZE',
                            49: 'E_ZCL_ERR_INVALID_IMAGE_VERSION',
                            50: 'E_ZCL_READ_ATTR_REQ_NOT_FINISHED',
                            51: 'E_ZCL_DENY_ATTRIBUTE_ACCESS',
                            52: 'E_ZCL_ERR_SECURITY_FAIL',
                            53: 'E_ZCL_ERR_CLUSTER_COMMAND_NOT_FOUND',
                            54: 'E_ZCL_ERR_SCENE_NOT_FOUND',
                            55: 'E_ZCL_RESTORE_DEFAULT_REPORT_CONFIGURATION',
                            56: 'E_ZCL_ERR_ENUM_END',
                            }
        return status_codes.get(self.data.get('status'),
                                ZCL_status_codes.get(self.data.get('status'),
                                'Failed (ZigBee event codes) 0x{:02x}'.format(self.data.get('status'))))


@register_response
class R8001(Response):
    msg = 0x8001
    type = 'Log message'
    s = OrderedDict([('level', 'B')])


@register_response
class R8002(Response):
    msg = 0x8002
    type = 'Data indication'
    s = OrderedDict([('status', 'B'),
                     ('profile_id', 'H'),
                     ('cluster_id', 'H'),
                     ('source_endpoint', 'B'),
                     ('destination_endpoint', 'B'),
                     # ('source_address_mode', 'B'),
                     # ('source_address', 'H'),
                     # ('dst_address_mode', 'B'),
                     # ('dst_address', 'H'),
                     # ('payload_size', 'B'),
                     # ('payload', 'rawend')
                     ])

    def decode(self):
        Response.decode(self)
        additional = self.data.pop('additional')
        source_address_mode = struct.unpack('!B', additional[:1])[0]
        self.data['source_address_mode'] = source_address_mode
        additional = additional[1:]
        if source_address_mode == 3:
            source_address = struct.unpack('!Q', additional[:8])[0]
            source_address = '{:016x}'.format(source_address)
            additional = additional[8:]
        else:
            source_address = struct.unpack('!H', additional[:2])[0]
            source_address = '{:04x}'.format(source_address)
            additional = additional[2:]
        self.data['source_address'] = source_address

        dst_address_mode = struct.unpack('!B', additional[:1])[0]
        self.data['dst_address_mode'] = dst_address_mode
        additional = additional[1:]
        if dst_address_mode == 3:
            dst_address = struct.unpack('!Q', additional[:8])[0]
            dst_address = '{:016x}'.format(dst_address)
            additional = additional[8:]
        else:
            dst_address = struct.unpack('!H', additional[:2])[0]
            dst_address = '{:04x}'.format(dst_address)
            additional = additional[2:]
        self.data['dst_address'] = dst_address
#         payload_size = struct.unpack('!B', additional[:1])[0]
#         self.data['payload_size'] = payload_size
        self.data['payload'] = additional


@register_response
class R8003(Response):
    msg = 0x8003
    type = 'Clusters list'
    s = OrderedDict([('endpoint', 'B'),
                     ('profile_id', 'H'),
                     ('clusters', OrderedDict([('cluster', 'H')]))
                     ])


@register_response
class R8004(Response):
    msg = 0x8004
    type = 'Attribute list'
    s = OrderedDict([('endpoint', 'B'),
                     ('profile_id', 'H'),
                     ('cluster', 'H'),
                     ('attributes', OrderedDict([('attribute', 'H')]))
                     ])


@register_response
class R8005(Response):
    msg = 0x8005
    type = 'Command list'
    s = OrderedDict([('endpoint', 'B'),
                     ('profile_id', 'H'),
                     ('cluster', 'H'),
                     ('commands', OrderedDict([('command', 'B')]))
                     ])


@register_response
class R8006(Response):
    msg = 0x8006
    type = 'Non “Factory new” Restart'
    s = OrderedDict([('status', 'B'),
                     ])


@register_response
class R8007(Response):
    msg = 0x8007
    type = '“Factory New” Restart'
    s = OrderedDict([('status', 'B'),
                     ])


@register_response
class R8009(Response):
    msg = 0x8009
    type = 'Network state response'
    s = OrderedDict([('addr', 'H'),
                     ('ieee', 'Q'),
                     ('panid', 'H'),
                     ('extended_panid', 'Q'),
                     ('channel', 'B'),
                     ])


@register_response
class R8010(Response):
    msg = 0x8010
    type = 'Version list'
    s = OrderedDict([('major', 'H'),
                     ('installer', 'H')])
    format = {'installer': '{:x}',
              }

    def decode(self):
        Response.decode(self)
        self.data['version'] = '{}.{}'.format(self.data['installer'][0],
                                              self.data['installer'][1:])


@register_response
class R8011(Response):
    msg = 0x8011
    type = 'APS_DATA_ACK'
    s = OrderedDict([('status', 'B'),
                     ('addr', 'H'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ])


@register_response
class R8014(Response):
    msg = 0x8014
    type = 'Permit join status'
    s = OrderedDict([('status', '?')])


@register_response
class R8015(Response):
    msg = 0x8015
    type = 'Device list'
    s = OrderedDict([('devices', OrderedDict([('id', 'B'),
                                              ('addr', 'H'),
                                              ('ieee', 'Q'),
                                              ('power_type', 'B'),
                                              ('lqi', 'B')]))])


@register_response
class R8017(Response):
    msg = 0x8017
    type = 'TimeServer'
    s = OrderedDict([('timestamp', 'L'),
                     ])


@register_response
class R8024(Response):
    msg = 0x8024
    type = 'Network joined / formed'
    s = OrderedDict([('status', 'B'),
                     ])

    def decode(self):
        Response.decode(self)
        if self.data['status'] < 2:
            data = self.data.pop('additional')
            data = struct.unpack('!HQB', data)
            self.data['addr'] = data[0]
            self.data['ieee'] = data[1]
            self.data['channel'] = data[2]
            self._format(self.data)


@register_response
class R802B(Response):
    msg = 0x802B
    type = 'User Descriptor Notify'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H')
                     ])


@register_response
class R802C(Response):
    msg = 0x802C
    type = 'User Descriptor Response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H'),
                     ('length', 'B'),
                     ('data', 'rawend')
                     ])


@register_response
class R8030(Response):
    msg = 0x8030
    type = 'Bind response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 2:  # firmware < 3.1a
            self.s = self.s.copy()
            del self.s['address_mode']
            del self.s['addr']
        Response.decode(self)


@register_response
class R8031(R8030):
    msg = 0x8031
    type = 'unBind response'


@register_response
class R8035(Response):
    msg = 0x8035
    type = 'PDM Event'
    s = OrderedDict([('status', 'B'),
                     ('record', 'I'),
                     ])

    def status_text(self):
        status_codes = ['E_PDM_SYSTEM_EVENT_WEAR_COUNT_TRIGGER_VALUE_REACHED',
                        'E_PDM_SYSTEM_EVENT_DESCRIPTOR_SAVE_FAILED',
                        'E_PDM_SYSTEM_EVENT_PDM_NOT_ENOUGH_SPACE',
                        'E_PDM_SYSTEM_EVENT_LARGEST_RECORD_FULL_SAVE_NO_LONGER_POSSIBLE',
                        'E_PDM_SYSTEM_EVENT_SEGMENT_DATA_CHECKSUM_FAIL',
                        'E_PDM_SYSTEM_EVENT_SEGMENT_SAVE_OK',
                        'E_PDM_SYSTEM_EVENT_EEPROM_SEGMENT_HEADER_REPAIRED',
                        'E_PDM_SYSTEM_EVENT_SYSTEM_INTERNAL_BUFFER_WEAR_COUNT_SWAP',
                        'E_PDM_SYSTEM_EVENT_SYSTEM_DUPLICATE_FILE_SEGMENT_DETECTED',
                        'E_PDM_SYSTEM_EVENT_SYSTEM_ERROR',
                        'E_PDM_SYSTEM_EVENT_SEGMENT_PREWRITE',
                        'E_PDM_SYSTEM_EVENT_SEGMENT_POSTWRITE',
                        'E_PDM_SYSTEM_EVENT_SEQUENCE_DUPLICATE_DETECTED',
                        'E_PDM_SYSTEM_EVENT_SEQUENCE_VERIFY_FAIL',
                        'E_PDM_SYSTEM_EVENT_PDM_SMART_SAVE',
                        'E_PDM_SYSTEM_EVENT_PDM_FULL_SAVE',
                        ]
        try:
            return status_codes[self.data.get('status')]
        except IndexError:
            return 'Unknown PDM event'



@register_response
class R8040(Response):
    msg = 0x8040
    type = 'Network Address response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('ieee', 'Q'),
                     ('addr', 'H'),
                     ('count', 'B'),
                     ('index', 'B'),
                     ('devices', OrderedDict([('addr', 'H')]))
                     ])


@register_response
class R8041(R8040):
    msg = 0x8041
    type = 'IEEE Address response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('ieee', 'Q'),
                     ('addr', 'H'),
                     ('count', 'B'),
                     ('index', 'B'),
                     ('devices', OrderedDict([('ieee', 'Q')]))
                     ])


@register_response
class R8042(Response):
    msg = 0x8042
    type = 'Node descriptor'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H'),
                     ('manufacturer_code', 'H'),
                     ('max_rx', 'H'),
                     ('max_tx', 'H'),
                     ('server_mask', 'H'),
                     ('descriptor_capability', 'B'),
                     ('mac_capability', 'B'),
                     ('max_buffer', 'B'),
                     ('bit_field', 'H')
                     ])
    format = {'addr': '{:04x}',
              'manufacturer_code': '{:04x}',
              'descriptor_capability': '{:08b}',
              'mac_capability': '{:08b}',
              'bit_field': '{:016b}'}
#     Bitfields:
#     Logical type (bits 0-2
#     0 – Coordinator
#     1 – Router
#     2 – End Device)
#     Complex descriptor available (bit 3)
#     User descriptor available (bit 4)
#     Reserved (bit 5-7)
#     APS flags (bit 8-10 – currently 0)
#     Frequency band(11-15 set to 3 (2.4Ghz))

#     Server mask bits:
#     0 – Primary trust center
#     1 – Back up trust center
#     2 – Primary binding cache
#     3 – Backup binding cache
#     4 – Primary discovery cache
#     5 – Backup discovery cache
#     6 – Network manager
#     7 to15 – Reserved

#     MAC capability
#     Bit 0 – Alternate PAN Coordinator
#     Bit 1 – Device Type
#     Bit 2 – Power source
#     Bit 3 – Receiver On when Idle
#     Bit 4-5 – Reserved
#     Bit 6 – Security capability
#     Bit 7 – Allocate Address

#     Descriptor capability:
#     0 – extended Active endpoint list available
#     1 – Extended simple descriptor list available
#     2 to 7 – Reserved

    def cleaned_data(self):
        return self._filter_data(exclude=['sequence', 'status'])

    @property
    def extended_active_endpoint_list(self):
        return self.data['descriptor_capability'][0] == '1'

    @property
    def extended_simple_descriptor_list(self):
        return self.data['descriptor_capability'][1] == '1'


@register_response
class R8043(Response):
    msg = 0x8043
    type = 'Simple descriptor'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H'),
                     ('length', 'B'),
                     ('endpoint', 'B'),
                     ('profile', 'H'),
                     ('device', 'H'),
                     ('bit_field', 'B'),
                     ('inout_clusters', 'rawend')
                     ])
    format = {'addr': '{:04x}',
              'bit_field': '{:08b}'}

    def decode(self):
        Response.decode(self)
        data = self.data['inout_clusters']
        in_cluster_count = struct.unpack('!B', data[:1])[0]
        cluster_size = struct.calcsize('!H')
        in_clusters = struct.unpack('!{}H'.format(in_cluster_count),
                                    data[1:in_cluster_count * cluster_size + 1])
        data = data[in_cluster_count * 2 + 1:]
        out_cluster_count = struct.unpack('!B', data[:1])[0]
        out_clusters = struct.unpack('!{}H'.format(out_cluster_count),
                                     data[1:out_cluster_count * cluster_size + 1])
        self.data['in_clusters'] = in_clusters
        self.data['out_clusters'] = out_clusters

    def cleaned_data(self):
        return self._filter_data(['profile', 'device',
                                  'in_clusters', 'out_clusters'])


@register_response
class R8044(Response):
    msg = 0x8044
    type = 'Power descriptor'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('bit_field', 'H'),
                     ])
    format = {'bit_field': '{:016b}'}
    #     Bit fields
    # 0 to 3: current power mode
    # 4 to 7: available power source
    # 8 to 11: current power source
    # 12 to15: current power source level


@register_response
class R8045(Response):
    msg = 0x8045
    type = 'Active endpoints'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H'),
                     ('endpoint_count', 'B'),
                     ('endpoints', OrderedDict([('endpoint', 'B')]))
                     ])


@register_response
class R8046(Response):
    msg = 0x8046
    type = 'Match Descriptor response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('addr', 'H'),
                     ('match_count', 'B'),
                     ('matches', OrderedDict([('match', 'B')]))
                     ])


@register_response
class R8047(Response):
    msg = 0x8047
    type = 'Management Leave indication'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ])


@register_response
class R804A(Response):
    msg = 0x804A
    type = 'Management Network Update response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('total_transmission', 'H'),
                     ('transmission_failures', 'H'),
                     ('scanned_channels', 'L'),
                     ('channel_count', 'B'),
                     ])

    def decode(self):
        Response.decode(self)
        additional = self.data.pop('additional')
        if self.data['channel_count'] == len(additional):
            channels = struct.unpack('!{}B'.format(self.data['channel_count']), additional)
            self.data['channels'] = [OrderedDict([('channel', c)]) for c in channels]
        else:
            channels = struct.unpack('!{}BH'.format(self.data['channel_count']), additional)
            self.data['channels'] = [{'channel': c} for c in channels[:-1]]
            self.data['addr'] = channels[-1]
        self._format(self.data)


@register_response
class R8048(Response):
    msg = 0x8048
    type = 'Leave indication'
    s = OrderedDict([('ieee', 'Q'),
                     ('rejoin_status', 'B'),
                     ])


@register_response
class R004D(Response):
    msg = 0x004D
    type = 'Device announce'
    s = OrderedDict([('addr', 'H'),
                     ('ieee', 'Q'),
                     ('mac_capability', 'B'),
                     ('rejoin_status', '?'),
                     ])
    format = {'addr': '{:04x}',
              'ieee': '{:016x}',
              'mac_capability': '{:08b}'}
#     MAC capability
#     Bit 0 – Alternate PAN Coordinator
#     Bit 1 – Device Type
#     Bit 2 – Power source
#     Bit 3 – Receiver On when Idle
#     Bit 4,5 – Reserved
#     Bit 6 – Security capability
#     Bit 7 – Allocate Address

    def decode(self):
        if len(self.msg_data) < 12:  # fw < 3.1b
            self.s = self.s.copy()
            del self.s['rejoin_status']
        Response.decode(self)


@register_response
class R804E(Response):
    msg = 0x804E
    type = 'Management LQI response'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('entries', 'B'),
                     ('count', 'B'),
                     ('index', 'B'),
                     ])

    format = {'addr': '{:04x}',
              'ieee': '{:016x}',
              'bit_field': '{:08b}'}

    def decode(self):
        Response.decode(self)
        additional = self.data.pop('additional')
        neighbours = []
        for i in range(self.data['count']):
            if len(additional) < 3:
                break
            neighbour, additional = self._decode('!HQQBBB',
                                                 ['addr', 'extended_panid', 'ieee', 'depth', 'lqi', 'bit_field'],
                                                 additional)
            neighbours.append(neighbour)
        self.data['neighbours'] = neighbours
        if len(additional) >= 2:
            self.data['addr'] = struct.unpack('!H', additional)[0]
        if 'addr' not in self.data:  # firmware < 3.1a
            self.data['addr'] = 0xffff
        self._format(self.data)
# Bit map of attributes Described below: uint8_t
# {bit 0-1 Device Type
# (0-Coordinator 1-Router 2-End Device)
# bit 2-3 Permit Join status
# (1- On 0-Off)
# bit 4-5 Relationship
# (0-Parent 1-Child 2-Sibling)
# bit 6-7 Rx On When Idle status
# (1-On 0-Off)}


@register_response
class R8060(Response):
    msg = 0x8060
    type = 'Add group response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('group', 'H'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 7:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
        Response.decode(self)


@register_response
class R8061(Response):
    msg = 0x8061
    type = 'View group response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('group', 'H'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 7:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
        Response.decode(self)


@register_response
class R8062(Response):
    msg = 0x8062
    type = 'Get group membership'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     # ('addr', 'H'),  # firmware < 3.0f
                     ('capacity', 'B'),
                     ('group_count', 'B'),
                     # ('groups', OrderedDict([('group', 'H')])),
                     ])

    def decode(self):
        try:
            Response.decode(self)
            additional = self.data.pop('additional')
            d = struct.unpack('!{}HH'.format(self.data['group_count']), additional)
            self.data['groups'] = [{'group': gaddr} for gaddr in d[:-1]]
            self.data['addr'] = d[-1]
            self._format(self.data)
        except struct.error:  # probably old firmware < 3.0f
            self.s = OrderedDict([('sequence', 'B'),
                                  ('endpoint', 'B'),
                                  ('cluster', 'H'),
                                  ('addr', 'H'),  # firmware < 3.0f
                                  ('capacity', 'B'),
                                  ('group_count', 'B'),
                                  ('groups', OrderedDict([('group', 'H')])),
                                  ])
            Response.decode(self)

    def cleaned_data(self):
        self.data['groups'] = [g['group'] for g in self.data['groups']]
        return self.data


@register_response
class R8063(R8061):
    msg = 0x8063
    type = 'Remove group response'


@register_response
class R8085(Response):
    msg = 0x8085
    type = 'Remote button pressed (MOVE_TO_LEVEL_UPDATE)'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),
                     ('cmd', 'B'),
                     ])

    def decode(self):
        Response.decode(self)
        press_type = {2: 'click', 1: 'hold', 3: 'release'}
        if self.data['cmd'] in (1, 2, 3):
            self.data['button'] = 'down'
            self.data['type'] = press_type.get(self.data['cmd'], self.data['cmd'])
        elif self.data['cmd'] in (5, 6, 7):
            self.data['button'] = 'up'
            self.data['type'] = press_type.get(self.data['cmd'] - 4, self.data['cmd'])

    def cleaned_data(self):
        # fake attribute
        self.data['attribute'] = 0xfff0
        self.data['data'] = '{}_{}'.format(self.data['button'],
                                           self.data['type'])
        return self._filter_data(['attribute', 'data'])


@register_response
class R8095(Response):
    msg = 0x8095
    type = 'Remote button pressed (ONOFF_UPDATE)'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),
                     ('cmd', 'B'),
                     ])

    def decode(self):
        Response.decode(self)
        press_type = {2: 'click'}
        self.data['button'] = 'middle'
        self.data['type'] = press_type.get(self.data['cmd'], self.data['cmd'])

    def cleaned_data(self):
        # fake attribute
        self.data['attribute'] = 0xfff0
        self.data['data'] = '{}_{}'.format(self.data['button'],
                                           self.data['type'])
        return self._filter_data(['attribute', 'data'])


@register_response
class R80A0(Response):
    msg = 0x80A0
    type = 'View Scene response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('group', 'H'),
                     ('scene', 'B'),
                     ('transition', 'H'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 10:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
        Response.decode(self)


@register_response
class R80A1(Response):
    msg = 0x80A1
    type = 'Add Scene response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('group', 'H'),
                     ('scene', 'B'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 8:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
        Response.decode(self)


@register_response
class R80A2(R80A1):
    msg = 0x80A2
    type = 'Remove Scene response'


@register_response
class R80A3(Response):
    msg = 0x80A3
    type = 'Remove all Scenes response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('group', 'H'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 9:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
        Response.decode(self)


@register_response
class R80A4(R80A1):
    msg = 0x80A4
    type = 'Store Scene response'


@register_response
class R80A6(Response):
    msg = 0x80A6
    type = 'Scene membership response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('status', 'B'),
                     ('capacity', 'B'),
                     ('group', 'H'),
                     ('scene_count', 'B'),
                     # ('scenes', OrderedDict([('scene', 'B')])),
                     # ('addr', 'H'),
                     ])

    def decode(self):
        try:
            Response.decode(self)
            additional = self.data.pop('additional')
            d = struct.unpack('!{}BH'.format(self.data['scene_count']), additional)
            self.data['scenes'] = [{'scene': gaddr} for gaddr in d[:-1]]
            self.data['addr'] = d[-1]
            self._format(self.data, ['addr'])
        except (struct.error, KeyError):  # probably old firmware < 3.0f
            self.s = OrderedDict([('sequence', 'B'),
                                  ('endpoint', 'B'),
                                  ('cluster', 'H'),
                                  ('status', 'B'),
                                  ('capacity', 'B'),
                                  ('group', 'H'),
                                  ('scene_count', 'B'),
                                  ('scenes', OrderedDict([('scene', 'B')])),
                                  ])
            Response.decode(self)

    def cleaned_data(self):
        self.data['scenes'] = [g['scene'] for g in self.data['scenes']]
        return self.data


@register_response
class R80A7(Response):
    msg = 0x80A7
    type = 'Remote button pressed (LEFT/RIGHT)'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('cmd', 'B'),
                     ('direction', 'B'),
                     ('attr1', 'B'),
                     ('attr2', 'B'),
                     ('attr3', 'B'),
                     ('addr', 'H'),
                     ])

    def decode(self):
        Response.decode(self)
        directions = {0: 'right', 1: 'left', 2: 'middle'}
        press_type = {7: 'click', 8: 'hold', 9: 'release'}
        self.data['button'] = directions.get(self.data['direction'], self.data['direction'])
        self.data['type'] = press_type.get(self.data['cmd'], self.data['cmd'])
        if self.data['type'] == 'release':
            self.data['button'] = 'previous'

    def cleaned_data(self):
        # fake attribute
        self.data['attribute'] = 0xfff0
        self.data['data'] = '{}_{}'.format(self.data['button'],
                                           self.data['type'])
        return self._filter_data(['attribute', 'data'])


@register_response
class R8100(Response):
    msg = 0x8100
    type = 'Read Attribute response'
    s = OrderedDict([('sequence', 'B'),
                     ('addr', 'H'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('attribute', 'H'),
                     ('status', 'B'),
                     ('data_type', 'B'),
                     ('size', 'H'),
                     ('data', 'rawend')
                     ])

    def decode(self):
        Response.decode(self)
        fmt = DATA_TYPE.get(self.data['data_type'], 's')
        length = self.data['size']
        # https://github.com/fairecasoimeme/ZiGate/issues/134
        # workaround because of type 0x25 unsupported
        if self.data['data_type'] not in DATA_TYPE:
            length = len(self.data['data'])
        fmt = '!{}{}'.format(length // struct.calcsize(fmt), fmt)
        data = struct.unpack(fmt, self.data['data'])[0]
        if isinstance(data, bytes):
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = hexlify(data).decode()
        self.data['data'] = data

    def cleaned_data(self):
        return self._filter_data(['attribute', 'data'])


@register_response
class R8101(Response):
    msg = 0x8101
    type = 'Default device response'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('cmd', 'B'),
                     ('status', 'B'),
                     ])


@register_response
class R8102(R8100):
    msg = 0x8102
    type = 'Individual Attribute Report'


@register_response
class R8110(R8100):
    msg = 0x8110
    type = 'Write Attribute response'


@register_response
class R8120(Response):
    msg = 0x8120
    type = 'Configure Reporting response'
    s = OrderedDict([('sequence', 'B'),
                     ('addr', 'H'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('attribute', 'H'),
                     ('status', 'B'),
                     ])

    def decode(self):
        if len(self.msg_data) == 7:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['attribute']
        Response.decode(self)


@register_response
class R8140(Response):
    msg = 0x8140
    type = 'Attribute Discovery response'
    s = OrderedDict([('complete', 'B'),
                     ('data_type', 'B'),
                     ('attribute', 'H'),
                     ('addr', 'H'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ])

    def decode(self):
        if len(self.msg_data) == 4:  # firmware < 3.0f
            self.s = self.s.copy()
            del self.s['addr']
            del self.s['endpoint']
            del self.s['cluster']
        Response.decode(self)

    def cleaned_data(self):
        return self._filter_data(['attribute'])


@register_response
class R8401(Response):
    msg = 0x8401
    type = 'IAS Zone Status Change'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),  # ou Q suivant mode
                     ('zone_status', 'H'),
                     ('status', 'B'),
                     ('zone_id', 'B'),
                     ('delay', 'H'),
                     ])

    format = {'addr': '{:04x}',
              'zone_status': '{:016b}'}

    def cleaned_data(self):
        return self._filter_data(['addr', 'zone_status', 'zone_id'])


@register_response
class R8501(Response):
    msg = 0x8501
    type = 'OTA image block request'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),
                     ('node_address', 'Q'),
                     ('file_offset', 'L'),
                     ('image_version', 'L'),
                     ('image_type', 'H'),
                     ('manufacturer_code', 'H'),
                     ('block_request_delay', 'H'),
                     ('max_data_size', 'B'),
                     ('field_control', 'B')
                     ])


@register_response
class R8503(Response):
    msg = 0x8503
    type = 'OTA upgrade end request'
    s = OrderedDict([('sequence', 'B'),
                     ('endpoint', 'B'),
                     ('cluster', 'H'),
                     ('address_mode', 'B'),
                     ('addr', 'H'),
                     ('file_version', 'L'),
                     ('image_type', 'H'),
                     ('manufacture_code', 'H'),
                     ('status', 'B')
                     ])


@register_response
class R8701(Response):
    msg = 0x8701
    type = 'Route Discovery Confirmation'
    s = OrderedDict([('status', 'B'),
                     ('network_status', 'B'),
                     ])


@register_response
class R8702(Response):
    msg = 0x8702
    type = 'APS Data Confirm Fail'
    s = OrderedDict([('status', 'B'),
                     ('source_endpoint', 'B'),
                     ('dst_endpoint', 'B'),
                     ('dst_address_mode', 'B'),
                     # ('dst_address', 'Q'),
                     # ('sequence', 'B')
                     ])

    format = {'dst_address': '{:016x}'}

    def decode(self):
        if len(self.msg_data) < 13:
            self.format = self.format.copy()
            self.format = {'dst_address': '{:04x}'}
            self.s = self.s.copy()
            self.s['dst_address'] = 'H'
            self.s['sequence'] = 'B'
        Response.decode(self)
        if 'additional' in self.data:
            additional = self.data.pop('additional')
            self.data['dst_address'], self.data['sequence'] = struct.unpack('!QB', additional)
            self.data['dst_address'] = '{:016x}'.format(self.data['dst_address'])
            if self.data['dst_address_mode'] == 2:
                self.data['dst_address'] = self.data['dst_address'][:4]


@register_response
class R8806(Response):
    msg = 0x8806
    type = 'Set TX POWER'
    s = OrderedDict([('raw_level', 'B'),
                     ('level', 'B'),
                     ])

    def decode(self):
        Response.decode(self)
        self.data['percent'] = self.data['level'] * 100 // 255


@register_response
class R8807(R8806):
    msg = 0x8807
    type = 'Get TX POWER'
