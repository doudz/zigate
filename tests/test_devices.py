'''
ZiGate devices Tests
-------------------------
'''

import unittest
from zigate import core
import json
import os
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

        device.set_attribute(1, 6, {'attribute': 0, 'rssi': 255, 'data': False, 'inverse': True})
        device.set_attribute(1, 0, {'attribute': 1, 'rssi': 255, 'data': 'test'})

        device.generate_template(self.test_dir)
        with open(os.path.join(self.test_dir, 'lumi.weather.json')) as fp:
            jdata = json.load(fp)
        self.assertEqual(jdata,
                         {'endpoints': [{'clusters': [{'attributes': [{'attribute': 4, 'data': 'LUMI'},
                                                                      {'attribute': 5, 'data': 'lumi.weather'},
                                                                      {'attribute': 7, 'data': 3}], 'cluster': 0},
                                                      {'attributes': [{'attribute': 0}], 'cluster': 1026},
                                                      {'attributes': [{'attribute': 0}, {'attribute': 16},
                                                                      {'attribute': 20}], 'cluster': 1027},
                                                      {'attributes': [{'attribute': 0}], 'cluster': 1029},
                                                      {'attributes': [{'attribute': 0, 'inverse': True}],
                                                       'cluster': 6}],
                                         'device': 24321, 'endpoint': 1,
                                         'in_clusters': [0, 3, 65535, 1026, 1027, 1029],
                                         'out_clusters': [0, 4, 65535], 'profile': 260}],
                          'generictype': 'sensor',
                          'info': {'bit_field': '0100000000000010',
                                   'descriptor_capability': '00000000',
                                   'mac_capability': '10000000',
                                   'manufacturer_code': '1037',
                                   'power_type': 0,
                                   'server_mask': 0}}
                         )

    def test_inverse_bool(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'lumi.sensor_switch.aq2'})
        device.set_attribute(1, 6, {'attribute': 0, 'rssi': 255, 'data': True})
        self.assertTrue(device.get_property_value('onoff'))
        device.load_template()
        device.set_attribute(1, 6, {'attribute': 0, 'rssi': 255, 'data': True})
        self.assertFalse(device.get_property_value('onoff'))

    def test_templates(self):
        path = os.path.join(core.BASE_PATH, 'templates')
        files = os.listdir(path)
        for f in files:
            success = False
            try:
                with open(os.path.join(path, f)) as fp:
                    json.load(fp)
                success = True
            except Exception:
                pass
            self.assertTrue(success)

    def test_reset_attribute(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0x0101, {'attribute': 0x0503, 'rssi': 255, 'data': 12.0})
        self.assertEqual(device.get_property_value('rotation'), 12.0)
        device._reset_attribute(1, 0x0101, 0x0503)
        self.assertEqual(device.get_property_value('rotation'), 0.0)
        device.set_attribute(1, 0x0101, {'attribute': 0x0503, 'rssi': 255, 'data': 'test'})
        self.assertEqual(device.get_property_value('rotation'), 0.0)
        device._reset_attribute(1, 0x0101, 0x0503)
        self.assertEqual(device.get_property_value('rotation'), 0.0)


if __name__ == '__main__':
    unittest.main()
