'''
ZiGate Transport Tests
-------------------------
'''

import unittest
from zigate import mqtt_broker
from zigate import responses


class TestMQTT(unittest.TestCase):
    def test_jsonResponse(self):
        r = responses.R8000(b'\x00\x00\x00\x01', 255)
        mqtt_broker.json.encoder
        mqtt_broker.json.dumps(r, cls=mqtt_broker.DeviceEncoder)


if __name__ == '__main__':
    unittest.main()
