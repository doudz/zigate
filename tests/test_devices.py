'''
ZiGate devices Tests
-------------------------
'''

import unittest
from zigate import core
import json
import tempfile
import shutil


class TestCore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_device_dump(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'test'})
        last_seen = device.info['last_seen']
        data = json.dumps(device, cls=core.DeviceEncoder, sort_keys=True)
        self.maxDiff = None
        self.assertEqual(data,
                         ('{"addr": "1234", "discovery": "", "endpoints": [{"clusters": [{"attributes": '
                          '[{"attribute": 5, "data": '
                          '"test", "name": "type", "type": "str", "value": "test"}], "cluster": 0}], "device": 0, '
                          '"endpoint": 1, "in_clusters": [], "out_clusters": [], "profile": 0}], "generictype": "", '
                          '"info": {"addr": "1234", "ieee": "0123456789abcdef", "last_seen": "' + last_seen + '", '
                          '"rssi": 255}}'))

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
        self.assertEqual(device.discovery, 'templated')
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

        device.generate_template(self.test_dir)


if __name__ == '__main__':
    unittest.main()
