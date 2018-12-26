'''
ZiGate devices Tests
-------------------------
'''

import unittest
from zigate import core
import json


class TestCore(unittest.TestCase):
    def test_device_dump(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'test'})
        last_seen = device.info['last_seen']
        data = json.dumps(device, cls=core.DeviceEncoder)
        self.assertEqual(data,
                         ('{"addr": "1234", "info": {"addr": "1234", "ieee": "0123456789abcdef", '
                          '"rssi": 255, "last_seen": "' + last_seen + '"}, "endpoints": [{"endpoint": 1, '
                          '"clusters": [{"cluster": 0, "attributes": [{"attribute": 5, "data": "test", '
                          '"name": "type", "value": "test", "type": "str"}]}], "profile": 0, "device": 0, '
                          '"in_clusters": [], "out_clusters": []}], "generictype": ""}'))

    def test_template(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'lumi.test'})
        self.assertFalse(device.load_template())

        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        self.assertFalse(device.load_template())
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'lumi.weather'})

        self.assertCountEqual(device.properties,
                              [{'attribute': 5, 'data': 'lumi.weather',
                                'name': 'type', 'value': 'lumi.weather', 'type': str}]
                              )
        self.assertEqual(device.genericType, '')
        self.assertTrue(device.load_template())
        self.assertEqual(device.genericType, 'sensor')
        self.assertCountEqual(device.properties,
                              [{'attribute': 4, 'data': 'LUMI', 'name': 'manufacturer', 'value': 'LUMI'},
                               {'attribute': 5, 'data': 'lumi.weather', 'name': 'type', 'value': 'lumi.weather',
                                'type': str},
                               {'attribute': 7, 'data': 3, 'name': 'power_source', 'value': 3},
                               {'attribute': 0, 'name': 'temperature', 'unit': '°C', 'value': 0.0, 'type': float},
                               {'attribute': 0, 'name': 'pressure', 'unit': 'mb', 'value': 0, 'type': int},
                               {'attribute': 16, 'name': 'pressure2', 'unit': 'mb', 'value': 0.0, 'type': float},
                               {'attribute': 0, 'name': 'humidity', 'unit': '%', 'value': 0.0, 'type': float}]
                              )


if __name__ == '__main__':
    unittest.main()
