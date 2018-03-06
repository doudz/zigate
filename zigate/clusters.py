'''
Created on 12 févr. 2018

@author: doudz
'''
import struct
from binascii import unhexlify, hexlify
import logging


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
                                      {'value': attribute['data']})
            except:
                LOGGER.error('Failed to eval "{}" using "{}"'.format(attribute['value'],
                                                                     attribute['data']
                                                                     ))
                attribute['value'] = None
        return added

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


@register_cluster
class C0000(Cluster):
    cluster_id = 0x0000
    type = 'General: Basic'
    attributes_def = {0x0004: {'name': 'manufacturer', 'value': 'value'},
                      0x0005: {'name': 'type', 'value': 'value'},
                      0x0006: {'name': 'datecode', 'value': 'value'},
                      0x0007: {'name': 'power_source', 'value': 'value'},
                      0xff01: {'name': 'battery', 'value': "struct.unpack('H', unhexlify(value)[2:4])[0]/1000.", 'unit': 'V'},
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
                      0x8000: {'name': 'multiclick', 'value': 'value'},
                      }


@register_cluster
class C0008(Cluster):
    cluster_id = 0x0008
    type = 'General: Level control'
    attributes_def = {0x0000: {'name': 'current_level', 'value': 'value'},
                      }


@register_cluster
class C000c(Cluster):
    cluster_id = 0x000c
    type = 'Xiaomi cube: Rotation'
    attributes_def = {0xff05: {'name': 'rotation', 'value': 'value'},
                      }


@register_cluster
class C0012(Cluster):
    cluster_id = 0x0012
    type = 'Xiaomi cube: Movement'
    attributes_def = {0x0055: {'name': 'movement', 'value': 'value'},
                      }


@register_cluster
class C0402(Cluster):
    cluster_id = 0x0402
    type = 'Measurement: Temperature'
    attributes_def = {0x0000: {'name': 'temperature', 'value': 'value/100.', 'unit': '°C'},
                      }


@register_cluster
class C0403(Cluster):
    cluster_id = 0x0403
    type = 'Measurement: Atmospheric Pressure'
    attributes_def = {0x0000: {'name': 'pressure', 'value': 'value', 'unit': 'mb'},
                      0x0010: {'name': 'pressure2', 'value': 'value/10.', 'unit': 'mb'},
                      }


@register_cluster
class C0405(Cluster):
    cluster_id = 0x0405
    type = 'Measurement: Humidity'
    attributes_def = {0x0000: {'name': 'humidity', 'value': 'value/100.', 'unit': '%'},
                      }


@register_cluster
class C0406(Cluster):
    cluster_id = 0x0406
    type = 'Measurement: Occupancy Sensing'
    attributes_def = {0x0000: {'name': 'presence', 'value': 'value'},
                      }
