'''
Created on 12 févr. 2018

@author: doudz
'''
import struct
from binascii import unhexlify, hexlify
import logging
import traceback

LOGGER = logging.getLogger('zigate')


# CLUSTERS = {0x0000: 'General: Basic',
#             0x0001: 'General: Power Config',
#             0x0002: 'General: Temperature Config',
#             0x0003: 'General: Identify',
#             0x0004: 'General: Groups',
#             0x0005: 'General: Scenes',
#             0x0006: 'General: On/Off',
#             0x0007: 'General: On/Off Config',
#             0x0008: 'General: Level Control',
#             0x0009: 'General: Alarms',
#             0x000A: 'General: Time',
#             0x000F: 'General: Binary Input Basic',
#             0x0020: 'General: Poll Control',
#             0x0019: 'General: OTA',
#             0x0101: 'General: Door Lock',
#             0x0201: 'HVAC: Thermostat',
#             0x0202: 'HVAC: Fan Control',
#             0x0300: 'Lighting: Color Control',
#             0x0400: 'Measurement: Illuminance',
#             0x0402: 'Measurement: Temperature',
#             0x0403: 'Measurement: Atmospheric Pressure',
#             0x0405: 'Measurement: Humidity',
#             0x0406: 'Measurement: Occupancy Sensing',
#             0x0500: 'Security & Safety: IAS Zone',
#             0x0702: 'Smart Energy: Metering',
#             0x0B05: 'Misc: Diagnostics',
#             0x1000: 'ZLL: Commissioning',
#             0xFF01: 'Xiaomi private',
#             0xFF02: 'Xiaomi private',
#             0x1234: 'Xiaomi private'
#             }

CLUSTERS = {}


def register_cluster(o):
    CLUSTERS[o.cluster_id] = o
    return o


def get_cluster(cluster_id):
    cls_cluster = CLUSTERS.get(cluster_id, Cluster)
    cluster = cls_cluster()
    if type(cluster) == Cluster:
        cluster.cluster_id = cluster_id
    return cluster


def clean_str(text):
    text = text.replace('\x00', '')
    text = text.strip()
    return text


class Cluster(object):
    cluster_id = None
    type = 'Unknown cluster'
    attributes_def = {}

    def __init__(self):
        self.attributes = {}

    def update(self, data):
        attribute_id = data['attribute']
        added = False
        if attribute_id not in self.attributes:
            self.attributes[attribute_id] = {}
            added = True
        attribute = self.attributes[attribute_id]
        attribute.update(data)
        attr_def = self.attributes_def.get(attribute_id)
        if attr_def:
            attribute.update(attr_def)
            try:
                attribute['value'] = eval(attribute['value'],
                                          globals(),
                                          {'value': attribute['data'],
                                           'self': self})
            except:
                LOGGER.error('Failed to eval "{}" using "{}"'.format(attribute['value'],
                                                                     attribute['data']
                                                                     ))
                LOGGER.error(traceback.format_exc())
                attribute['value'] = None
        return (added, attribute)

    def __str__(self):
        return 'Cluster 0x{:04x} {}'.format(self.cluster_id, self.type)

    def __repr__(self):
        return self.__str__()

    def to_json(self):
        return {'cluster': self.cluster_id,
                'attributes': list(self.attributes.values())
                }

    @staticmethod
    def from_json(data):
        cluster_id = data['cluster']
        cluster = CLUSTERS.get(cluster_id, Cluster)
        cluster = cluster()
        if type(cluster) == Cluster:
            cluster.cluster_id = cluster_id
        for attribute in data['attributes']:
            cluster.update(attribute)
        return cluster

    def get_attribute(self, attribute_id):
        return self.attributes.get(attribute_id, {})

    def get_property(self, name):
        '''
        return attribute matching name
        '''
        for attribute in self.attributes.values():
            if attribute.get('name') == name:
                return attribute

    def has_property(self, name):
        '''
        check attribute matching name exist
        '''
        return self.get_property(name) is not None


@register_cluster
class C0000(Cluster):
    cluster_id = 0x0000
    type = 'General: Basic'
    attributes_def = {0x0000: {'name': 'zcl_version', 'value': 'value'},
                      0x0001: {'name': 'application_version', 'value': 'value'},
                      0x0002: {'name': 'stack_version', 'value': 'value'},
                      0x0003: {'name': 'hardware_version', 'value': 'value'},
                      0x0004: {'name': 'manufacturer',
                               'value': 'clean_str(value)'},
                      0x0005: {'name': 'type', 'value': 'clean_str(value)'},
                      0x0006: {'name': 'datecode', 'value': 'value'},
                      0x0007: {'name': 'power_source', 'value': 'value'},
                      0x0010: {'name': 'description',
                               'value': 'clean_str(value)'},
                      0xff01: {'name': 'battery',
                               'value': "struct.unpack('H', unhexlify(value)[2:4])[0]/1000.",
                               'unit': 'V'},
                      }

    def update(self, data):
        if data['attribute'] == 0xff01 and not data['data'].startswith('0121'):
            return
        return Cluster.update(self, data)


@register_cluster
class C0001(Cluster):
    cluster_id = 0x0001
    type = 'General: Power Config'
    attributes_def = {0x0000: {'name': 'voltage', 'value': 'value'},
                      0x0020: {'name': 'battery_voltage', 'value': 'value'},
                      0x0021: {'name': 'battery_percent', 'value': 'value'},
                      0x0030: {'name': 'battery_manufacturer', 'value': 'value'},
                      0x0031: {'name': 'battery_size', 'value': 'value'},
                      0x0033: {'name': 'battery_quantity', 'value': 'value'},
                      }
#     battery_size
#     E_CLD_PWRCFG_BATTERY_SIZE_NO_BATTERY= 0x00,
#     E_CLD_PWRCFG_BATTERY_SIZE_BUILT_IN,
#     E_CLD_PWRCFG_BATTERY_SIZE_OTHER,
#     E_CLD_PWRCFG_BATTERY_SIZE_AA,
#     E_CLD_PWRCFG_BATTERY_SIZE_AAA,
#     E_CLD_PWRCFG_BATTERY_SIZE_C,
#     E_CLD_PWRCFG_BATTERY_SIZE_D,
#     E_CLD_PWRCFG_BATTERY_SIZE_UNKNOWN     = 0xff,


@register_cluster
class C0006(Cluster):
    cluster_id = 0x0006
    type = 'General: On/Off'
    attributes_def = {0x0000: {'name': 'onoff', 'value': 'value'},
                      0x8000: {'name': 'multiclick', 'value': 'value',
                               'expire': 2},
                      }


@register_cluster
class C0008(Cluster):
    cluster_id = 0x0008
    type = 'General: Level control'
    attributes_def = {0x0000: {'name': 'current_level', 'value': 'int(value*100/254)'},
                      }


@register_cluster
class C000c(Cluster):
    cluster_id = 0x000c
    type = 'Analog input (Xiaomi cube: Rotation)'
    attributes_def = {0x0055: {'name': 'rotation_angle?', 'value': 'value',
                               'expire': 2},
                      0xff05: {'name': 'rotation', 'value': 'value',
                               'expire': 2},
                      }


#         +---+
#         | 2 |
#     +---+---+---+
#     | 4 | 0 | 1 |
#     +---+---+---+
#         | 5 |
#         +---+
#         | 3 |
#         +---+
#     Side 5 is with the MI logo; side 3 contains the battery door.
#
#     Shake: 0x0000 (side on top doesn't matter)
#     90º Flip from side x on top to side y on top: 0x0040 + (x << 3) + y
#     180º Flip to side x on top: 0x0080 + x
#     Push while side x is on top: 0x0100 + x
#     Double Tap while side x is on top: 0x0200 + x
#     Push works in any direction.
#     For Double Tap you really need to lift the cube and tap it on the table twice.

def cube_decode(value):
    if value == '' or value is None:
        return value
    events = {0x0000: 'shake',
              0x0002: 'wakeup',
              0x0003: 'drop',
              }
    if value in events:
        return events[value]
    elif value & 0x0080 != 0:  # flip180
        face = value ^ 0x0080
        value = 'flip180_{}'.format(face)
    elif value & 0x0100 != 0:  # push
        face = value ^ 0x0100
        value = 'push_{}'.format(face)
    elif value & 0x0200 != 0:  # double_tap
        face = value ^ 0x0200
        value = 'double_tap_{}'.format(face)
    else:  # flip90
        face = value ^ 0x0040
        face1 = face >> 3
        face2 = face ^ (face1 << 3)
        value = 'flip90_{}{}'.format(face1, face2)
    return value


@register_cluster
class C0012(Cluster):
    cluster_id = 0x0012
    type = 'Multistate input (Xiaomi cube: Movement)'
    attributes_def = {0x0055: {'name': 'movement', 'value': 'cube_decode(value)',
                               'expire': 2, 'expire_value': ''},
                      }


@register_cluster
class C0300(Cluster):
    cluster_id = 0x0300
    type = 'Lighting: Color Control'
    attributes_def = {0x0000: {'name': 'current_hue', 'value': 'int(value*360/254)'},
                      0x0001: {'name': 'current_saturation', 'value': 'int(value*100/254)'},
                      0x0002: {'name': 'remaining_time', 'value': 'value'},
                      0x0003: {'name': 'current_x', 'value': 'value/65536'},
                      0x0004: {'name': 'current_y', 'value': 'value/65536'},
                      0x0005: {'name': 'drift', 'value': 'value'},
                      0x0006: {'name': 'compensation', 'value': 'value'},
                      0x0007: {'name': 'colour_temperature', 'value': '1000000//value'},
                      0x0008: {'name': 'colour_mode', 'value': 'value'},
                      0x0010: {'name': 'nb_primaries', 'value': 'value'},
                      0x0011: {'name': 'primary_1_x', 'value': 'value'},
                      0x0012: {'name': 'primary_1_y', 'value': 'value'},
                      0x0013: {'name': 'primary_1_intensity', 'value': 'value'},
                      0x0015: {'name': 'primary_2_x', 'value': 'value'},
                      0x0016: {'name': 'primary_2_y', 'value': 'value'},
                      0x0017: {'name': 'primary_2_intensity', 'value': 'value'},
                      0x0019: {'name': 'primary_3_x', 'value': 'value'},
                      0x0020: {'name': 'primary_3_y', 'value': 'value'},
                      0x0021: {'name': 'primary_3_intensity', 'value': 'value'},
                      0x400a: {'name': 'capabilities', 'value': 'value'},
                      0x400b: {'name': 'temperature_phy_min', 'value': 'value'},
                      0x400c: {'name': 'temperature_phy_max', 'value': 'value'},
                      }


@register_cluster
class C0400(Cluster):
    cluster_id = 0x0400
    type = 'Measurement: Illuminance'
    attributes_def = {0x0000: {'name': 'luminosity', 'value': 'value',
                               'unit': 'lm'},
                      0x0001: {'name': 'min_value', 'value': 'value',
                               'unit': 'lm'},
                      0x0002: {'name': 'max_value', 'value': 'value',
                               'unit': 'lm'},
                      }


@register_cluster
class C0402(Cluster):
    cluster_id = 0x0402
    type = 'Measurement: Temperature'
    attributes_def = {0x0000: {'name': 'temperature', 'value': 'value/100.',
                               'unit': '°C'},
                      }


@register_cluster
class C0403(Cluster):
    cluster_id = 0x0403
    type = 'Measurement: Atmospheric Pressure'
    attributes_def = {0x0000: {'name': 'pressure', 'value': 'value',
                               'unit': 'mb'},
                      0x0010: {'name': 'pressure2', 'value': 'value/10.',
                               'unit': 'mb'},
                      }


@register_cluster
class C0405(Cluster):
    cluster_id = 0x0405
    type = 'Measurement: Humidity'
    attributes_def = {0x0000: {'name': 'humidity', 'value': 'value/100.',
                               'unit': '%'},
                      }


@register_cluster
class C0406(Cluster):
    cluster_id = 0x0406
    type = 'Measurement: Occupancy Sensing'
    attributes_def = {0x0000: {'name': 'presence', 'value': 'bool(value)',
                               'expire': 10},
                      }


@register_cluster
class C0500(Cluster):
    cluster_id = 0x0500
    type = 'Security & Safety: IAS Zone'
    attributes_def = {255: {'name': 'zone_status', 'value': 'self._decode(value[::-1])'},
#                       0: {'name': 'alarm1', 'value': 'bool(value)'},
#                       1: {'name': 'alarm2', 'value': 'bool(value)'},
#                       2: {'name': 'tamper', 'value': 'bool(value)'},
#                       3: {'name': 'low_battery', 'value': 'bool(value)'},
#                       4: {'name': 'supervision', 'value': 'bool(value)'},
#                       5: {'name': 'restore', 'value': 'bool(value)'},
#                       6: {'name': 'trouble', 'value': 'bool(value)'},
#                       7: {'name': 'ac_fault', 'value': 'bool(value)'},
#                       8: {'name': 'test_mode', 'value': 'bool(value)'},
#                       9: {'name': 'battery_defect', 'value': 'bool(value)'},
                      }

    def update(self, data):
        zone_id = data['zone_id']
        data['attribute'] = zone_id
        data['data'] = data['zone_status']
        # if zone_id is unknown, clone defaut zone
        if zone_id not in self.attributes_def:
            self.attributes_def[zone_id] = self.attributes_def[255]
        r = Cluster.update(self, data)
        return r

    def _decode(self, zone_status):
        fields = ['alarm1',
                  'alarm2',
                  'tamper',
                  'low_battery',
                  'supervision',
                  'restore',
                  'trouble',
                  'ac_fault',
                  'test_mode',
                  'battery_defect'
                  ]
        zone = {}
        for i, field in enumerate(fields):
            bit = zone_status[i]
            zone[field] = bool(int(bit))
        return zone
# b16ZoneStatus is a mandatory attribute which is a 16-bit bitmap indicating
# the status of each of the possible notification triggers from the device:
# Bit
# 
# Description
# 0 Alarm1:
# 1 - Opened or alarmed
# 0 - Closed or not alarned
# 1 Alarm2:
# 1 - Opened or alarmed
# 0 - Closed or not alarned
# 2 Tamper:
# 1 - Tampered with
# 0 - Not tampered with
# 3 Battery:
# 1 - Low
# 0 - OK
# 4 Supervision reports 1 :
# 1 - Reports
# 0 - No reports
# 5 Restore reports 2 :
# 1 - Reports
# 0 - No reports
# 6 Trouble:
# 1 - Trouble/failure
# 0 - OK
# 7 AC (mains):
# 1 - Fault
# 0 - OK
# 8 Test mode:
# 1 - Sensor in test mode
# 0 - Sensor in operational mode
# 9 Battery defect:
# 1 - Defective battery detected
# 0 - Battery OK
# 10-15
# Reserved
