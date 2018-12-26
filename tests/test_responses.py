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

    def test_response_8140(self):
        msg_data = b'\x01\x10\x00\x12'
        r = responses.R8140(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('complete', 1),
                                          ('attribute_type', 16),
                                          ('attribute_id', 18),
                                          ('rssi', 255)]))

    def test_response_8062(self):
        msg_data = b'\x01\x01\x00\x04\x124\x10\x01\x98v'
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('groups', ['9876']),
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('addr', '1234'),
                                          ('capacity', 16),
                                          ('group_count', 1),
                                          ('rssi', 255)]))

        msg_data = b'\x01\x01\x00\x04\x124\x10\x00'
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('groups', []),
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('addr', '1234'),
                                          ('capacity', 16),
                                          ('group_count', 0),
                                          ('rssi', 255)]))


if __name__ == '__main__':
    unittest.main()
