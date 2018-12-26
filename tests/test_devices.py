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
                          '"rssi": 255, "last_seen": "'+last_seen+'"}, "endpoints": [{"endpoint": 1, '
                          '"clusters": [{"cluster": 0, "attributes": [{"attribute": 5, "data": "test", '
                          '"name": "type", "value": "test", "type": "str"}]}], "profile": 0, "device": 0, '
                          '"in_clusters": [], "out_clusters": []}]}'))


if __name__ == '__main__':
    unittest.main()
