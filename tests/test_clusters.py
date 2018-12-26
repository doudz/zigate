'''
ZiGate clusters Tests
-------------------------
'''

import unittest
from zigate import clusters, core
import json


class TestResponses(unittest.TestCase):
    def test_cluster_0012(self):
        # xiaomi cube status
        endpoint = {'device': 24321}
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
                               'name': 'multiclick', 'value': 4,
                               'type': int}}
                         )

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


if __name__ == '__main__':
    unittest.main()
