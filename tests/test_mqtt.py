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
        payload = mqtt_broker.json.dumps(r, cls=mqtt_broker.DeviceEncoder)
        self.assertEqual(payload,
                         '{"status": 0, "sequence": 0, '
                         '"packet_type": 1, "error": "", "lqi": 255}')


if __name__ == '__main__':
    unittest.main()
