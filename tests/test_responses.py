'''
ZiGate responses Tests
-------------------------
'''

import unittest
from zigate import responses
from collections import OrderedDict
from binascii import unhexlify


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
        self.assertDictEqual(r.data,
                             OrderedDict([('complete', 1),
                                          ('data_type', 16),
                                          ('attribute', 18),
                                          ('rssi', 255)]))
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('attribute', 18),
                                          ]))

    def test_response_8140_30f(self):
        # response from firmware 3.0f
        msg_data = b'\x000\x00\x08\x93-\x03\x03\x00'
        r = responses.R8140(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('complete', 0),
                                          ('data_type', 48),
                                          ('attribute', 8),
                                          ('addr', '932d'),
                                          ('endpoint', 3),
                                          ('cluster', 768),
                                          ('rssi', 255)]))
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('attribute', 8),
                                          ]))

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

    def test_response_8060(self):
        msg_data = b'\x01\x01\x00\x04\x004\x10'
        r = responses.R8060(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('status', 0),
                                          ('group', '3410'),
                                          ('rssi', 255)])
                             )

    def test_response_8060_30f(self):
        msg_data = b'A\x03\x00\x04\x93-\x00\x124'
        r = responses.R8060(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 65),
                                          ('endpoint', 3),
                                          ('cluster', 4),
                                          ('addr', '932d'),
                                          ('status', 0),
                                          ('group', '1234'),
                                          ('rssi', 255)])
                             )

    def test_reponse_8102_vibration(self):
        msg_data = unhexlify(b'26a32301010105080025000800000448')
        r = responses.R8102(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 38),
                                          ('addr', 'a323'),
                                          ('endpoint', 1),
                                          ('cluster', 257),
                                          ('attribute', 0x0508),
                                          ('status', 0),
                                          ('data_type', 37),
                                          ('size', 8),
                                          ('data', '\x00\x00\x04H'),
                                          ('rssi', 255)])
                             )

    def test_response_8009(self):
        msg_data = unhexlify(b'00000123456789abcdef12340123456789abcdef0b')
        r = responses.R8009(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('addr', '0000'),
                                          ('ieee', '0123456789abcdef'),
                                          ('panid', 4660),
                                          ('extended_panid', 81985529216486895),
                                          ('channel', 11),
                                          ('rssi', 255)])
                             )


if __name__ == '__main__':
    unittest.main()
