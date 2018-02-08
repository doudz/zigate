'''
Created on 24 janv. 2018

@author: sramage
'''
import struct
from collections import OrderedDict
from binascii import unhexlify, hexlify

RESPONSES = {}

DATA_TYPE = {0x00: None,
             0x10: '?',
             0x18: 'b',
             0x20: 'B',
             0x21: 'H',
             0x22: 'I',
             0x25: 'L',
             0x28: 'b',
             0x29: 'h',
             0x2a: 'i',
             0x30: 'b',
             0x41: 'e',
             0x42: 's',
             }


def register_response(o):
    RESPONSES[o.msg] = o
    return o


class Response(object):
    msg = 0x0
    type = 'Base response'
    s = OrderedDict()
    format = {'addr': '{:04x}',
              'ieee': '{:08x}'}

    def __init__(self, msg_data, rssi):
        self.msg_data = msg_data
        self.rssi = rssi
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

    def get(self, key, default):
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
                rest = len(msg_data)-struct.calcsize(fmt)
                subfmt = '!'+''.join(v.values())
                count = rest//struct.calcsize(subfmt)
                submsg_data = msg_data[-rest:]
                msg_data = msg_data[:-rest]
                self.data[k] = []
                for i in range(count):
                    sdata, submsg_data = self.__decode(subfmt,
                                                       v.keys(),
                                                       submsg_data)
                    self.__format(sdata)
                    self.data[k].append(sdata)
            elif v == 'rawend':
                fmt += '{}s'.format(len(msg_data)-struct.calcsize(fmt))
            else:
                fmt += v
        sdata, msg_data = self.__decode(fmt, keys, msg_data)
        self.data.update(sdata)
        if msg_data:
            self.data['additionnal'] = msg_data

        # reformat output, TODO: do it live
        self.__format(self.data)
        self.data['rssi'] = self.rssi

    def __decode(self, fmt, keys, data):
        size = struct.calcsize(fmt)
        sdata = OrderedDict(zip(keys, struct.unpack(fmt, data[:size])))
        data = data[size:]
        return sdata, data

    def __format(self, data):
        for k in data.keys():
            if k in self.format:
                data[k] = self.format[k].format(data[k])


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
        return status_codes.get(self.data.get('status'),
                                'Failed (ZigBee event codes) {}'.format(self.data.get('status')))


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
                     ('source_address_mode', 'B'),
                     ('source_address', 'H'),
                     ('destination_address_mode', 'B'),
                     ('destination_address', 'H'),
                     ('payload_size', 'B'),
                     ('payload', 'rawend')
                     ])

    def decode(self):
        Response.decode(self)
        self.data['payload'] = struct.unpack('!{}B'.format(self.data['payload_size']),
                                             self.data['payload'])[0]


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
        fmt = '!{}{}'.format(self.data['size']//struct.calcsize(fmt), fmt)
        data = struct.unpack(fmt, self.data['data'])[0]
        if isinstance(data, bytes):
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = hexlify(data).decode()
        self.data['data'] = data

    def cleaned_data(self):
        d = {'addr': self.data['addr'],
             'endpoint': self.data['endpoint'],
             'cluster': self.data['cluster'],
             'attribute': self.data['attribute'],
             'status': self.data['status'],
             'data': self.data['data'],
             }
        return d


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
class R8014(Response):
    msg = 0x8014
    type = 'Permit join status'
    s = OrderedDict([('status', '?')])


@register_response
class R8015(Response):
    msg = 0x8015
    type = 'Device list'
    s = OrderedDict([('devices', OrderedDict([
                                            ('id', 'B'),
                                            ('addr', 'H'),
                                            ('ieee', 'Q'),
                                            ('power_source', 'B'),
                                            ('link_quality', 'B'),
                                            ]))])


@register_response
class R8024(Response):
    msg = 0x8024
    type = 'Network joined / formed'
    s = OrderedDict([('status', 'B'),
                     ('addr', 'H'),
                     ('ieee', 'Q'),
                     ('channel', 'B')
                     ])


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
#                      ('in_cluster_count', 'B')
#                      ('in_clusters', OrderedDict([('cluster', 'H')]))
#                      ('out_cluster_count', 'B')
#                      ('out_clusters', OrderedDict([('cluster', 'H')]))
                     ])
    format = {'bit_field': '{:08b}'}

    def decode(self):
        Response.decode(self)
        data = self.data['inout_clusters']
        in_cluster_count = struct.unpack('!B', data[0])[0]
        in_clusters = struct.unpack('!{}H'.format(in_cluster_count),data[1:in_cluster_count])
        data = data[in_cluster_count+1:]
        out_cluster_count = struct.unpack('!B', data[0])[0]
        out_clusters = struct.unpack('!{}H'.format(out_cluster_count),data[1:out_cluster_count])
        self.data['in_clusters'] = in_clusters
        self.data['out_clusters'] = out_clusters


@register_response
class R8044(Response):
    msg = 0x8044
    type = 'Power descriptor'
    s = OrderedDict([('sequence', 'B'),
                     ('status', 'B'),
                     ('bit_field', 'H'),
                     ])
    format = {'bit_field': '{:016b}'}


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
                     ('mac_capability', 'rawend')
                     ])
#     MAC capability
#     Bit 0 – Alternate PAN Coordinator
#     Bit 1 – Device Type
#     Bit 2 – Power source
#     Bit 3 – Receiver On when Idle
#     Bit 4,5 – Reserved
#     Bit 6 – Security capability
#     Bit 7 – Allocate Address


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
                     ('dst_address', 'Q'),
                     ('sequence', 'B')
                     ])
