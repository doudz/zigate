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


class FakeZiGate(object):
    def __getattr__(self, *args):
        return self.dummy

    def dummy(self, *args, **kwargs):
        pass


class TestCore(unittest.TestCase):
    def setUp(self):
        core.WAIT_TIMEOUT = 2 * core.SLEEP_INTERVAL  # reduce timeout during test
        self.zigate = FakeZiGate()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_device_dump(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'test'})
        last_seen = device.info['last_seen']
        data = json.dumps(device, cls=core.DeviceEncoder, sort_keys=True)
        self.maxDiff = None
        self.assertEqual(data,
                         ('{"addr": "1234", "discovery": "", "endpoints": [{"clusters": [{"attributes": '
                          '[{"attribute": 5, "data": '
                          '"test", "name": "type", "type": "str", "value": "test"}], "cluster": 0}], "device": 0, '
                          '"endpoint": 1, "in_clusters": [], "out_clusters": [], "profile": 0}], "generictype": "", '
                          '"info": {"addr": "1234", "ieee": "0123456789abcdef", "last_seen": "' + last_seen + '", '
                          '"lqi": 255}}'))

    def test_template(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.test'})
        self.assertFalse(device.load_template())

        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        self.assertFalse(device.load_template())
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.weather'})

        self.assertCountEqual(device.properties,
                              [{'attribute': 5, 'data': 'lumi.weather',
                                'name': 'type', 'value': 'lumi.weather', 'type': str}]
                              )
        device.set_attribute(1, 0x0402, {'attribute': 0, 'lqi': 255, 'data': 1200})
        self.assertEqual(device.get_property_value('temperature'), 12.0)
        device.set_attribute(1, 0, {'attribute': 1, 'lqi': 255, 'data': 'test'})
        self.assertEqual(device.genericType, '')
        self.assertTrue(device.load_template())
        self.assertEqual(device.discovery, 'templated')
        self.assertEqual(device.genericType, 'sensor')
        self.assertCountEqual(device.properties,
                              [{'attribute': 1, 'data': 'test', 'name': 'application_version', 'value': 'test'},
                               {'attribute': 4, 'data': 'LUMI', 'name': 'manufacturer', 'value': 'LUMI'},
                               {'attribute': 5, 'data': 'lumi.weather', 'name': 'type', 'value': 'lumi.weather',
                                'type': str},
                               {'attribute': 7, 'data': 3, 'name': 'power_source', 'value': 3},
                               {'attribute': 0, 'data': 1200, 'name': 'temperature', 'value': 12.0, 'unit': '°C',
                                'type': float},
                               {'attribute': 0, 'name': 'pressure', 'unit': 'mb', 'value': 0, 'type': int},
                               {'attribute': 16, 'name': 'pressure2', 'unit': 'mb', 'value': 0.0, 'type': float},
                               {'attribute': 0, 'name': 'humidity', 'unit': '%', 'value': 0.0, 'type': float}]
                              )

        device.set_attribute(1, 6, {'attribute': 0, 'lqi': 255, 'data': False, 'inverse': True})
        device.set_attribute(1, 0, {'attribute': 1, 'lqi': 255, 'data': 'test'})

        device.generate_template(self.test_dir)
        with open(os.path.join(self.test_dir, 'lumi.weather.json')) as fp:
            jdata = json.load(fp)
        self.assertCountEqual(jdata,
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
        # another test
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        self.assertFalse(device.load_template())
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.sensor_wleak.aq1'})
        self.assertTrue(device.load_template())
        self.assertEqual(device.discovery, 'templated')
        self.assertEqual(device.genericType, 'sensor')
        self.assertDictEqual(device.get_property_value('zone_status'),
                             {'alarm1': False, 'alarm2': False, 'tamper': False, 'low_battery': False,
                              'supervision': False, 'restore': False, 'trouble': False, 'ac_fault': False,
                              'test_mode': False, 'battery_defect': False}
                             )

        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.sensor_cube'})
        self.assertTrue(device.load_template())
        self.assertCountEqual(device.attributes,
                              [{'endpoint': 1, 'cluster': 0, 'attribute': 5, 'data': 'lumi.sensor_cube',
                                'name': 'type', 'value': 'lumi.sensor_cube', 'type': str},
                               {'endpoint': 1, 'cluster': 0, 'attribute': 4, 'data': 'LUMI',
                                'name': 'manufacturer', 'value': 'LUMI'},
                               {'endpoint': 1, 'cluster': 0, 'attribute': 7, 'data': 3,
                                'name': 'power_source', 'value': 3},
                               {'endpoint': 2, 'cluster': 18, 'attribute': 85, 'name': 'movement',
                                'value': '', 'expire': 2, 'expire_value': '', 'type': str},
                               {'endpoint': 3, 'cluster': 12, 'attribute': 65285, 'name': 'rotation_time',
                                'value': 0, 'unit': 'ms', 'expire': 2, 'type': int},
                               {'endpoint': 3, 'cluster': 12, 'attribute': 85, 'name': 'rotation',
                                'value': 0.0, 'unit': '°', 'expire': 2, 'type': float}]
                              )

        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.remote.b186acn01'})
        self.assertTrue(device.load_template())
        self.assertCountEqual(device.attributes,
                              [{'endpoint': 1, 'cluster': 0, 'attribute': 5, 'data': 'lumi.remote.b186acn01',
                                'name': 'type', 'value': 'lumi.remote.b186acn01', 'type': str},
                               {'endpoint': 1, 'cluster': 18, 'attribute': 85, 'name': 'multiclick',
                                'value': '', 'expire': 2, 'type': str}]
                              )

        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.remote.b286acn01'})
        self.assertTrue(device.load_template())
        self.assertCountEqual(device.attributes,
                              [{'endpoint': 1, 'cluster': 0, 'attribute': 5, 'data': 'lumi.remote.b286acn01',
                                'name': 'type', 'value': 'lumi.remote.b286acn01', 'type': str},
                               {'endpoint': 1, 'cluster': 18, 'attribute': 85, 'name': 'multiclick',
                                'value': '', 'expire': 2, 'type': str},
                               {'endpoint': 2, 'cluster': 18, 'attribute': 85, 'name': 'multiclick2',
                                'value': '', 'expire': 2, 'type': str},
                               {'endpoint': 3, 'cluster': 18, 'attribute': 85, 'name': 'multiclick3',
                                'value': '', 'expire': 2, 'type': str}]
                              )

    def test_inverse_bool(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'}, self.zigate)
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': 'lumi.sensor_switch.aq2'})
        device.set_attribute(1, 6, {'attribute': 0, 'lqi': 255, 'data': True})
        self.assertTrue(device.get_property_value('onoff'))
        device.load_template()
        device.set_attribute(1, 6, {'attribute': 0, 'lqi': 255, 'data': True})
        self.assertFalse(device.get_property_value('onoff'))

    def test_templates(self):
        path = os.path.join(core.BASE_PATH, 'templates')
        files = os.listdir(path)
        for f in files:
            success = False
            try:
                print('Test template', f)
                with open(os.path.join(path, f)) as fp:
                    json.load(fp)
                device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'}, self.zigate)
                device.set_attribute(1, 0, {'attribute': 5, 'lqi': 255, 'data': f[:-5]})
                self.assertTrue(device.load_template())
                success = True
            except Exception as e:
                print(e)
            self.assertTrue(success)

    def test_reset_attribute(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0x0101, {'attribute': 0x0503, 'lqi': 255, 'data': 12.0})
        self.assertEqual(device.get_property_value('rotation'), 12.0)
        device._reset_attribute(1, 0x0101, 0x0503)
        self.assertEqual(device.get_property_value('rotation'), 0.0)
        device.set_attribute(1, 0x0101, {'attribute': 0x0503, 'lqi': 255, 'data': 'test'})
        self.assertEqual(device.get_property_value('rotation'), 0.0)
        device._reset_attribute(1, 0x0101, 0x0503)
        self.assertEqual(device.get_property_value('rotation'), 0.0)


if __name__ == '__main__':
    unittest.main()
