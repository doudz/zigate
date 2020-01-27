'''
ZiGate responses Tests
-------------------------
'''

import unittest
from zigate import responses, core
from collections import OrderedDict
from binascii import unhexlify
import json


class TestResponses(unittest.TestCase):
    def test_jsonResponse(self):
        r = responses.R8000(b'\x00\x00\x00\x01', 255)
        payload = json.dumps(r, cls=core.DeviceEncoder)
        self.assertEqual(payload,
                         '{"status": 0, "sequence": 0, '
                         '"packet_type": 1, "error": "", "lqi": 255}')

    def test_response_8000(self):
        msg_data = unhexlify(b'00010001')
        r = responses.R8000(msg_data, 255)
        self.assertEqual(r.status_text(), 'Success')
        msg_data = unhexlify(b'05010001')
        r = responses.R8000(msg_data, 255)
        self.assertEqual(r.status_text(), 'Stack already started (no new configuration accepted)')
        msg_data = unhexlify(b'15010001')
        r = responses.R8000(msg_data, 255)
        self.assertEqual(r.status_text(), 'E_ZCL_ERR_ZTRANSMIT_FAIL')
        msg_data = unhexlify(b'aa010001')
        r = responses.R8000(msg_data, 255)
        self.assertEqual(r.status_text(), 'Failed (ZigBee event codes) 0xaa')

    def test_response_8002(self):
        msg_data = unhexlify(b'0001000006020102123402abcd0401234567')
        r = responses.R8002(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('status', 0),
                                         ('profile_id', 256),
                                         ('cluster_id', 6),
                                         ('source_endpoint', 2),
                                         ('destination_endpoint', 1),
                                         ('lqi', 255),
                                         ('source_address_mode', 2),
                                         ('source_address', '1234'),
                                         ('dst_address_mode', 2),
                                         ('dst_address', 'abcd'),
                                         ('payload', b'\x04\x01#Eg')])
                             )
        msg_data = unhexlify(b'00010000060201030123456789abcdef03fedcba98765432100401234567')
        r = responses.R8002(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('status', 0),
                                          ('profile_id', 256),
                                          ('cluster_id', 6),
                                          ('source_endpoint', 2),
                                          ('destination_endpoint', 1),
                                          ('lqi', 255),
                                          ('source_address_mode', 3),
                                          ('source_address', '0123456789abcdef'),
                                          ('dst_address_mode', 3),
                                          ('dst_address', 'fedcba9876543210'),
                                          ('payload', b'\x04\x01#Eg')])
                             )

    def test_response_8024(self):
        # good status
        msg_data = b'\x01\x124\x00\x00\x00\x00\x00\x00\x00\x00\x01'
        r = responses.R8024(msg_data, 255)
        self.assertEqual(r.cleaned_data(),
                         OrderedDict([('status', 1),
                                      ('lqi', 255),
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
                                          ('lqi', 255)]),
                             )

    def test_response_8140(self):
        msg_data = b'\x01\x10\x00\x12'
        r = responses.R8140(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('complete', 1),
                                          ('data_type', 16),
                                          ('attribute', 18),
                                          ('lqi', 255)]))
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
                                          ('lqi', 255)]))
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('attribute', 8),
                                          ]))

    def test_response_8062(self):
        msg_data = unhexlify(b'01010004123410019876')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 1),
                                          ('lqi', 255),
                                          ('groups', ['9876']),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000412341000')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 0),
                                          ('lqi', 255),
                                          ('groups', []),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000412341002abcd9876')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 2),
                                          ('lqi', 255),
                                          ('groups', ['abcd', '9876']),
                                          ('addr', '1234'),
                                          ]))

    def test_response_8062_30f(self):
        msg_data = unhexlify(b'01010004100198761234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 1),
                                          ('lqi', 255),
                                          ('groups', ['9876']),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'0101000410001234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 0),
                                          ('lqi', 255),
                                          ('groups', []),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'010100041002abcd98761234')
        r = responses.R8062(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 4),
                                          ('capacity', 16),
                                          ('group_count', 2),
                                          ('lqi', 255),
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
                                          ('lqi', 255)])
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
                                          ('lqi', 255)])
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
                                          ('lqi', 255)])
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
                                          ('lqi', 255)])
                             )

    def test_response_804E(self):
        msg_data = unhexlify(b'e6000e02001d4ddb95a5201556ccd800158d0001e56372'
                             b'01b01a1e02db95a5201556ccd800158d0001e45b44016f1a')
        r = responses.R804E(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 230), ('status', 0), ('entries', 14),
                                          ('count', 2), ('index', 0),
                                          ('lqi', 255),
                                          ('neighbours', [OrderedDict([('addr', '1d4d'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e56372'), ('depth', 1),
                                                                      ('lqi', 176), ('bit_field', '00011010')]),
                                                          OrderedDict([('addr', '1e02'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e45b44'), ('depth', 1),
                                                                      ('lqi', 111), ('bit_field', '00011010')])]),
                                          ('addr', 'ffff')
                                          ])
                             )
        msg_data = unhexlify(b'e6000e02001d4ddb95a5201556ccd800158d0001e56372'
                             b'01b01a1e02db95a5201556ccd800158d0001e45b44016f1aabcd')
        r = responses.R804E(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 230), ('status', 0), ('entries', 14),
                                          ('count', 2), ('index', 0),
                                          ('lqi', 255),
                                          ('neighbours', [OrderedDict([('addr', '1d4d'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e56372'), ('depth', 1),
                                                                      ('lqi', 176), ('bit_field', '00011010')]),
                                                          OrderedDict([('addr', '1e02'),
                                                                      ('extended_panid', 15822734423051652312),
                                                                      ('ieee', '00158d0001e45b44'), ('depth', 1),
                                                                      ('lqi', 111), ('bit_field', '00011010')])]),
                                          ('addr', 'abcd')
                                          ])
                             )
        msg_data = unhexlify(b'38c10701060000')
        r = responses.R804E(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 56), ('status', 193), ('entries', 7),
                                          ('count', 1), ('index', 6),
                                          ('lqi', 255),
                                          ('neighbours', []),
                                          ('addr', '0000')
                                          ])
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
                                          ('lqi', 255)]))

        msg_data = unhexlify(b'01123401000600')
        r = responses.R8120(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('addr', '1234'),
                                          ('endpoint', 1),
                                          ('cluster', 6),
                                          ('status', 0),
                                          ('lqi', 255)]))

    def test_response_80A0(self):
        msg_data = unhexlify(b'0101000500abcd0200001234')
        r = responses.R80A0(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('group', 'abcd'),
                                          ('scene', 2),
                                          ('transition', 0),
                                          ('addr', '1234'),
                                          ('lqi', 255)])
                             )
        msg_data = unhexlify(b'0101000500abcd020000')
        r = responses.R80A0(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('group', 'abcd'),
                                          ('scene', 2),
                                          ('transition', 0),
                                          ('lqi', 255)])
                             )

    def test_response_80A6_30f(self):
        msg_data = unhexlify(b'010100050010abcd01021234')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 1),
                                          ('lqi', 255),
                                          ('scenes', [2]),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'010100050010abcd001234')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 0),
                                          ('lqi', 255),
                                          ('scenes', []),
                                          ('addr', '1234'),
                                          ]))

        msg_data = unhexlify(b'010100050010abcd0201021234')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 2),
                                          ('lqi', 255),
                                          ('scenes', [1, 2]),
                                          ('addr', '1234'),
                                          ]))

    def test_response_80A6(self):
        msg_data = unhexlify(b'010100050010abcd0102')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 1),
                                          ('lqi', 255),
                                          ('scenes', [2]),
                                          ]))

        msg_data = unhexlify(b'010100050010abcd00')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 0),
                                          ('lqi', 255),
                                          ('scenes', []),
                                          ]))

        msg_data = unhexlify(b'010100050010abcd020102')
        r = responses.R80A6(msg_data, 255)
        self.assertDictEqual(r.cleaned_data(),
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('status', 0),
                                          ('capacity', 16),
                                          ('group', 'abcd'),
                                          ('scene_count', 2),
                                          ('lqi', 255),
                                          ('scenes', [1, 2]),
                                          ]))

    def test_response_80A7(self):
        msg_data = unhexlify(b'0101000501020102031234')
        r = responses.R80A7(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 1),
                                          ('endpoint', 1),
                                          ('cluster', 5),
                                          ('cmd', 1),
                                          ('direction', 2),
                                          ('attr1', 1),
                                          ('attr2', 2),
                                          ('attr3', 3),
                                          ('addr', '1234'),
                                          ('lqi', 255),
                                          ('button', 'middle'),
                                          ('type', 1),
                                          ]))

    def test_response_8702(self):
        msg_data = unhexlify(b'd40103020123456789abcdefb9')
        r = responses.R8702(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('status', 212),
                                          ('source_endpoint', 1),
                                          ('dst_endpoint', 3),
                                          ('dst_address_mode', 2),
                                          ('lqi', 255),
                                          ('dst_address', '0123'),
                                          ('sequence', 185),
                                          ]))

        msg_data = unhexlify(b'd40103030123456789abcdefb9')
        r = responses.R8702(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('status', 212),
                                          ('source_endpoint', 1),
                                          ('dst_endpoint', 3),
                                          ('dst_address_mode', 3),
                                          ('lqi', 255),
                                          ('dst_address', '0123456789abcdef'),
                                          ('sequence', 185),
                                          ]))

        msg_data = unhexlify(b'd40101026eadb5')
        r = responses.R8702(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('status', 212),
                                          ('source_endpoint', 1),
                                          ('dst_endpoint', 1),
                                          ('dst_address_mode', 2),
                                          ('dst_address', '6ead'),
                                          ('sequence', 181),
                                          ('lqi', 255)]))

    def test_response_804A(self):
        msg_data = unhexlify(b'01000002000100000001020102')
        r = responses.R804A(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 1),
                                          ('status', 0),
                                          ('total_transmission', 2),
                                          ('transmission_failures', 1),
                                          ('scanned_channels', 1),
                                          ('channel_count', 2),
                                          ('lqi', 255),
                                          ('channels', [OrderedDict([('channel', 1)]),
                                                        OrderedDict([('channel', 2)])]),
                                          ])
                             )

        msg_data = unhexlify(b'01000002000100000001020102abcd')
        r = responses.R804A(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 1),
                                          ('status', 0),
                                          ('total_transmission', 2),
                                          ('transmission_failures', 1),
                                          ('scanned_channels', 1),
                                          ('channel_count', 2),
                                          ('lqi', 255),
                                          ('channels', [OrderedDict([('channel', 1)]),
                                                        OrderedDict([('channel', 2)])]),
                                          ('addr', 'abcd')
                                          ])
                             )

    def test_response_8030(self):
        msg_data = unhexlify(b'0100')
        r = responses.R8030(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 1),
                                          ('status', 0),
                                          ('lqi', 255),
                                          ])
                             )

        msg_data = unhexlify(b'010002abcd0001')
        r = responses.R8030(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 1),
                                          ('status', 0),
                                          ('address_mode', 2),
                                          ('addr', 'abcd'),
                                          ('cluster', 1),
                                          ('lqi', 255),
                                          ])
                             )

        msg_data = unhexlify(b'3200026ff0')
        r = responses.R8030(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('sequence', 50),
                                          ('status', 0),
                                          ('address_mode', 2),
                                          ('addr', '6ff0'),
                                          ('lqi', 255),
                                          ])
                             )

    def test_response_004d(self):
        msg_data = unhexlify(b'abcd0123456789abcdef01')  # fw < 3.1b
        r = responses.R004D(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('addr', 'abcd'),
                                          ('ieee', '0123456789abcdef'),
                                          ('mac_capability', '00000001'),
                                          ('lqi', 255),
                                          ])
                             )
        msg_data = unhexlify(b'abcd0123456789abcdef0101')  # fw >= 3.1b
        r = responses.R004D(msg_data, 255)
        self.assertDictEqual(r.data,
                             OrderedDict([('addr', 'abcd'),
                                          ('ieee', '0123456789abcdef'),
                                          ('mac_capability', '00000001'),
                                          ('rejoin_status', True),
                                          ('lqi', 255),
                                          ])
                             )


if __name__ == '__main__':
    unittest.main()
