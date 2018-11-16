'''
ZiGate responses Tests
-------------------------
'''

import unittest
from zigate import responses
from collections import OrderedDict


class TestResponses(unittest.TestCase):
    def test_response_8024(self):
        # good status
        msg_data = b'\x01\x124\x00\x00\x00\x00\x00\x00\x00\x00\x01'
        r = responses.R8024(msg_data, 255)
        self.assertEqual(r.cleaned_data(),
                         OrderedDict([('status', 1),
                                      ('rssi', 255),
                                      ('addr', '1234'),
                                      ('ieee', '0000000000000000'),
                                      ('channel', 1),
                                      ]),
                         )
        # bad status
        msg_data = b'\x04'
        r = responses.R8024(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('status', 4),
                                          ('rssi', 255)]),
                             )


if __name__ == '__main__':
    unittest.main()
