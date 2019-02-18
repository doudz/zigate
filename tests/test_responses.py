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
        msg_data = unhexlify(b'01010004123410019876')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 1),
                                          ('rssi', 255),
                                          ('groups', ['9876']),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000412341000')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 0),
                                          ('rssi', 255),
                                          ('groups', []),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000412341002abcd9876')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 2),
                                          ('rssi', 255),
                                          ('groups', ['abcd', '9876']),
                                          ('addr', '1234'),
                                          ]))

    def test_response_8062_30f(self):
        msg_data = unhexlify(b'01010004100198761234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 1),
                                          ('rssi', 255),
                                          ('groups', ['9876']),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000410001234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 0),
                                          ('rssi', 255),
                                          ('groups', []),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'010100041002abcd98761234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([
                                          ('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 2),
                                          ('rssi', 255),
                                          ('groups', ['abcd', '9876']),
                                          ('addr', '1234'),
                                          ]))

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
        msg_data = unhexlify(b'0a03000400932d1234')
        r = responses.R8060(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 10),
                                          ('endpoint', 3),
                                          ('cluster', 4),
                                          ('status', 0),
                                          ('group', '932d'),
                                          ('addr', '1234'),
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

    def test_response_804E(self):
        msg_data = unhexlify(b'e6000e02001d4ddb95a5201556ccd800158d0001e56372'
                             b'01b01a1e02db95a5201556ccd800158d0001e45b44016f1a')
        r = responses.R804E(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('neighbours', [OrderedDict([('addr', '1d4d'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e56372'), ('depth', 1),
                                                                      ('rssi', 176), ('bit_field', '00011010')]),
                                                          OrderedDict([('addr', '1e02'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e45b44'), ('depth', 1),
                                                                      ('rssi', 111), ('bit_field', '00011010')])]),
                                          ('sequence', 230), ('status', 0), ('entries', 14),
                                          ('count', 2), ('index', 0),
                                          ('rssi', 255)])
                             )

    def test_response_8120(self):
        msg_data = unhexlify(b'011234010006000000')
        r = responses.R8120(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('addr', '1234'),
                                          ('endpoint', 1),
                                          ('cluster', 6),
                                          ('attribute', 0),
                                          ('status', 0),
                                          ('rssi', 255)]))

        msg_data = unhexlify(b'01123401000600')
        r = responses.R8120(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('addr', '1234'),
                                          ('endpoint', 1),
                                          ('cluster', 6),
                                          ('status', 0),
                                          ('rssi', 255)]))


if __name__ == '__main__':
    unittest.main()
