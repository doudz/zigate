'''
ZiGate clusters Tests
-------------------------
'''

import unittest
from zigate import clusters, core
import json


class TestResponses(unittest.TestCase):
    def test_cluster_C0012(self):
        # xiaomi cube status
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(1, 0, {'attribute': 5, 'rssi': 255, 'data': 'lumi.sensor_cube'})
        endpoint = {'device': 24322}
        data = {"attributes": [{"attribute": 85,
                                "data": 4,
                                "expire": 2,
                                "expire_value": "",
                                "name": "movement",
                                "value": ""}],
                "cluster": 18
                }
        c = clusters.C0012.from_json(data, endpoint, device)
        self.assertEqual(c.attributes,
                         {85: {'attribute': 85, 'data': 4,
                               'expire': 2, 'expire_value': '',
                               'name': 'movement', 'value': 'flip90_84',
                               'type': str}}
                         )

        # xiaomi lumi.remote.b1acn01
        endpoint = {'device': 259}
        data = {"attributes": [{"attribute": 85,
                                "data": 4,
                                "expire": 2,
                                "expire_value": "",
                                "name": "movement",
                                "value": ""}],
                "cluster": 18
                }
        c = clusters.C0012.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {85: {'attribute': 85, 'data': 4,
                               'expire': 2,
                               'name': 'multiclick', 'value': '4',
                               'type': str}}
                         )

        # xiaomi lumi.remote.b286acn01
        endpoint = {'device': 24321}
        data = {"attributes": [{"attribute": 85,
                                "data": 1,
                                "expire": 2,
                                "name": "multiclick",
                                "value": ""}],
                "cluster": 18
                }
        c = clusters.C0012.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {85: {'attribute': 85, 'data': 1,
                               'expire': 2,
                               'name': 'multiclick', 'value': '1',
                               'type': str}}
                         )

    def test_cluster_C0000(self):
        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 5,
                                "data": 'test.test',
                                "name": "type",
                                "value": "test.test"}],
                "cluster": 0
                }
        c = clusters.C0000.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {5: {'attribute': 5, 'data': 'test.test',
                              'name': 'type', 'value': 'test.test', 'type': str}}
                         )
        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 5,
                                "data": 'test.test',
                                "name": "type",
                                "value": "test.test",
                                'type': 'str'}],
                "cluster": 0
                }
        c = clusters.C0000.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {5: {'attribute': 5, 'data': 'test.test',
                              'name': 'type', 'value': 'test.test', 'type': str}}
                         )
        jdata = json.dumps(c, cls=core.DeviceEncoder, sort_keys=True)
        self.assertEqual(jdata,
                         ('{"attributes": [{"attribute": 5, "data": "test.test", "name": "type", '
                          '"type": "str", "value": "test.test"}], "cluster": 0}'))

        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 65282,
                                "data": '100121e50b21a801240000000000217c012067',
                                }],
                "cluster": 0
                }
        c = clusters.C0000.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {65282: {'attribute': 65282, 'data': '100121e50b21a801240000000000217c012067',
                                  'name': 'battery_voltage', 'value': 3.045, 'type': float, 'unit': 'V'}}
                         )

        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 65282,
                                "data": '100021ef0b21a8012400000000002106002059',
                                }],
                "cluster": 0
                }
        c = clusters.C0000.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {65282: {'attribute': 65282, 'data': '100021ef0b21a8012400000000002106002059',
                                  'name': 'battery_voltage', 'value': 3.055, 'type': float, 'unit': 'V'}}
                         )

    def test_cluster_C0101(self):
        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 0x0503,
                                "data": '',
                                "name": "rotation",
                                "value": '',
                                "expire": 10,
                                "expire_value": ''
                                }],
                "cluster": 0x0101
                }
        c = clusters.C0101.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {0x0503: {'attribute': 0x0503, 'data': '', 'expire': 2,
                                   'unit': '°',
                                   'name': 'rotation', 'value': 0, 'type': float}}
                         )

    def test_inverse_bool(self):
        endpoint = {'device': 1}
        data = {"attributes": [{"attribute": 0,
                                "data": False,
                                "name": "onoff",
                                "value": False,
                                'inverse': True
                                }],
                "cluster": 0x0006
                }
        c = clusters.C0006.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {0: {'attribute': 0, 'data': False,
                              'inverse': True,
                              'name': 'onoff', 'value': True, 'type': bool}}
                         )
        data = {"attributes": [{"attribute": 0,
                                "data": True,
                                "name": "onoff",
                                "value": True,
                                'inverse': True
                                }],
                "cluster": 0x0006
                }
        c = clusters.C0006.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {0: {'attribute': 0, 'data': True,
                              'inverse': True,
                              'name': 'onoff', 'value': False, 'type': bool}}
                         )
        data = {"attributes": [{"attribute": 0,
                                "data": False,
                                "name": "onoff",
                                "value": False,
                                }],
                "cluster": 0x0006
                }
        c = clusters.C0006.from_json(data, endpoint)
        self.assertEqual(c.attributes,
                         {0: {'attribute': 0, 'data': False,
                              'name': 'onoff', 'value': False, 'type': bool}}
                         )

    def test_cluster_CFC00(self):
        data = {"attributes": [{"attribute": 1,
                                "data": '1'
                                }],
                "cluster": 0xFC00
                }
        c = clusters.CFC00.from_json(data)
        self.assertEqual(c.attributes,
                         {1: {'attribute': 1, 'data': '1', 'expire': 2,
                              'name': 'button_on', 'value': '1', 'type': str}}
                         )


if __name__ == '__main__':
    unittest.main()
