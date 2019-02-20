'''
ZiGate core Tests
-------------------------
'''

import unittest
import os
import shutil
import tempfile
from zigate import responses, transport, core
from binascii import hexlify, unhexlify
import time


class TestCore(unittest.TestCase):
    def setUp(self):
        core.WAIT_TIMEOUT = 2 * core.SLEEP_INTERVAL  # reduce timeout during test
#         self.zigate = ZiGate(auto_start=False)
#         self.zigate._addr = '0000'
#         self.zigate._ieee = '0123456789abcdef'
#         self.zigate.connection = transport.FakeTransport()
        self.zigate = core.FakeZiGate(auto_start=False)
        self.zigate.setup_connection()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_disable_persistent(self):
        self.zigate._path = None
        result = self.zigate.load_state()
        self.assertIsNone(result)
        self.zigate.start_auto_save()
        self.assertTrue(self.zigate._autosavetimer.is_alive())
        result = self.zigate.save_state()
        time.sleep(0.2)
        self.assertFalse(self.zigate._autosavetimer.is_alive())

    def test_persistent(self):
        path = os.path.join(self.test_dir, 'test_zigate.json')
        backup_path = path + '.0'

        result = self.zigate.load_state(path)
        self.assertFalse(result)

        with open(path, 'w') as fp:
            fp.write('fake file - test')
        result = self.zigate.load_state(path)
        self.assertFalse(result)

        os.remove(path)

        self.zigate.save_state(path)
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(backup_path))
        self.zigate.save_state(path)
        self.assertTrue(os.path.exists(backup_path))

        result = self.zigate.load_state(path)
        self.assertTrue(result)

        os.remove(path)
        os.remove(backup_path)

    def test_persistent_loading(self):
        data = '''{
    "devices": [
        {
            "addr": "23a7",
            "discovery": "templated",
            "endpoints": [
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 65281,
                                    "data": "0121db0b0328170421a81305211800062401000000000a210000",
                                    "name": "battery",
                                    "unit": "V",
                                    "value": 3.035
                                },
                                {
                                    "attribute": 4,
                                    "data": "LUMI",
                                    "name": "manufacturer",
                                    "value": "LUMI"
                                },
                                {
                                    "attribute": 5,
                                    "data": "lumi.sensor_switch.aq2",
                                    "name": "type",
                                    "type": "str",
                                    "value": "lumi.sensor_switch.aq2"
                                }
                            ],
                            "cluster": 0
                        },
                        {
                            "attributes": [
                                {
                                    "attribute": 0,
                                    "inverse": true,
                                    "name": "onoff",
                                    "type": "bool",
                                    "value": false
                                },
                                {
                                    "attribute": 32768,
                                    "expire": 2,
                                    "name": "multiclick",
                                    "type": "int",
                                    "value": 0
                                }
                            ],
                            "cluster": 6
                        }
                    ],
                    "device": 24321,
                    "endpoint": 1,
                    "in_clusters": [
                        0,
                        65535,
                        6
                    ],
                    "out_clusters": [
                        0,
                        4,
                        65535
                    ],
                    "profile": 260
                }
            ],
            "generictype": "",
            "info": {
                "addr": "23a7",
                "bit_field": "0100000000000010",
                "descriptor_capability": "00000000",
                "id": 6,
                "ieee": "00158d00016c487e",
                "last_seen": "2019-01-05 20:31:06",
                "mac_capability": "10000000",
                "manufacturer_code": "1037",
                "power_type": 0,
                "lqi": 135,
                "server_mask": 0
            }
        },
        {
            "addr": "8ddb",
            "discovery": "",
            "endpoints": [
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 65281,
                                    "data": "0121f90b03281d0421a8130521750006240100000000082104020a21000064100001",
                                    "name": "battery",
                                    "unit": "V",
                                    "value": 3.065
                                },
                                {
                                    "attribute": 5,
                                    "data": "lumi.sensor_wleak.aq1",
                                    "name": "type",
                                    "type": "str",
                                    "value": "lumi.sensor_wleak.aq1"
                                }
                            ],
                            "cluster": 0
                        },
                        {
                            "attributes": [
                                {
                                    "attribute": 255,
                                    "data": "0000000000000000",
                                    "name": "zone_status",
                                    "value": {
                                        "ac_fault": false,
                                        "alarm1": false,
                                        "alarm2": false,
                                        "battery_defect": false,
                                        "low_battery": false,
                                        "restore": false,
                                        "supervision": false,
                                        "tamper": false,
                                        "test_mode": false,
                                        "trouble": false
                                    }
                                }
                            ],
                            "cluster": 1280
                        }
                    ],
                    "device": 0,
                    "endpoint": 1,
                    "in_clusters": [],
                    "out_clusters": [],
                    "profile": 0
                }
            ],
            "generictype": "",
            "info": {
                "addr": "8ddb",
                "id": 3,
                "ieee": "00158d000214f45c",
                "last_seen": "2019-01-05 20:39:07",
                "power_type": 0,
                "lqi": 207
            }
        },
        {
            "addr": "c28c",
            "discovery": "",
            "endpoints": [
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 0,
                                    "data": 1,
                                    "name": "zcl_version",
                                    "value": 1
                                },
                                {
                                    "attribute": 1,
                                    "data": 31,
                                    "name": "application_version",
                                    "value": 31
                                },
                                {
                                    "attribute": 2,
                                    "data": 2,
                                    "name": "stack_version",
                                    "value": 2
                                },
                                {
                                    "attribute": 3,
                                    "data": 18,
                                    "name": "hardware_version",
                                    "value": 18
                                },
                                {
                                    "attribute": 4,
                                    "data": "LUMI",
                                    "name": "manufacturer",
                                    "value": "LUMI"
                                },
                                {
                                    "attribute": 5,
                                    "data": "lumi.ctrl_ln2.aq1",
                                    "name": "type",
                                    "type": "str",
                                    "value": "lumi.ctrl_ln2.aq1"
                                }
                            ],
                            "cluster": 0
                        },
                        {
                            "attributes": [
                                {
                                    "attribute": 0,
                                    "data": false,
                                    "name": "onoff",
                                    "type": "bool",
                                    "value": false
                                },
                                {
                                    "attribute": 61440,
                                    "data": 63081472
                                }
                            ],
                            "cluster": 6
                        }
                    ],
                    "device": 81,
                    "endpoint": 1,
                    "in_clusters": [
                        0,
                        4,
                        3,
                        6,
                        16,
                        5,
                        10,
                        1,
                        2
                    ],
                    "out_clusters": [
                        25,
                        10
                    ],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 0,
                                    "data": false,
                                    "name": "onoff2",
                                    "type": "bool",
                                    "value": false
                                },
                                {
                                    "attribute": 61440,
                                    "data": 63081472
                                }
                            ],
                            "cluster": 6
                        }
                    ],
                    "device": 81,
                    "endpoint": 2,
                    "in_clusters": [
                        6,
                        16
                    ],
                    "out_clusters": [],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 85,
                                    "data": 0.0,
                                    "expire": 2,
                                    "name": "rotation",
                                    "type": "float",
                                    "unit": "\u00b0",
                                    "value": 0.0
                                }
                            ],
                            "cluster": 12
                        }
                    ],
                    "device": 9,
                    "endpoint": 3,
                    "in_clusters": [
                        12
                    ],
                    "out_clusters": [
                        12,
                        4
                    ],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 85,
                                    "data": 0.0,
                                    "expire": 2,
                                    "name": "rotation4",
                                    "type": "float",
                                    "unit": "\u00b0",
                                    "value": 0.0
                                }
                            ],
                            "cluster": 12
                        }
                    ],
                    "device": 83,
                    "endpoint": 4,
                    "in_clusters": [
                        12
                    ],
                    "out_clusters": [
                        12
                    ],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 85,
                                    "data": "",
                                    "expire": 2,
                                    "expire_value": "",
                                    "name": "movement",
                                    "type": "str",
                                    "value": ""
                                }
                            ],
                            "cluster": 18
                        }
                    ],
                    "device": 0,
                    "endpoint": 5,
                    "in_clusters": [
                        16,
                        18
                    ],
                    "out_clusters": [],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 85,
                                    "data": "",
                                    "expire": 2,
                                    "expire_value": "",
                                    "name": "movement6",
                                    "type": "str",
                                    "value": ""
                                }
                            ],
                            "cluster": 18
                        }
                    ],
                    "device": 0,
                    "endpoint": 6,
                    "in_clusters": [
                        18,
                        16
                    ],
                    "out_clusters": [],
                    "profile": 260
                },
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 85,
                                    "data": "",
                                    "expire": 2,
                                    "expire_value": "",
                                    "name": "movement7",
                                    "type": "str",
                                    "value": ""
                                }
                            ],
                            "cluster": 18
                        }
                    ],
                    "device": 0,
                    "endpoint": 7,
                    "in_clusters": [
                        18,
                        16
                    ],
                    "out_clusters": [],
                    "profile": 260
                }
            ],
            "generictype": "",
            "info": {
                "addr": "c28c",
                "bit_field": "0100000000000001",
                "descriptor_capability": "00000000",
                "id": 53,
                "ieee": "00158d000232294f",
                "last_seen": "2019-01-23 10:35:21",
                "mac_capability": "10001110",
                "manufacturer_code": "115f",
                "max_buffer": 127,
                "max_rx": 100,
                "max_tx": 100,
                "power_type": 1,
                "lqi": 96,
                "server_mask": 0
            }
        }
        ],
    "groups": {
        "5a92": [
            [
                "a677",
                11
            ],
            [
                "fe1b",
                1
            ],
            [
                "edf0",
                1
            ],
            [
                "7ad1",
                1
            ],
            [
                "d7d0",
                1
            ],
            [
                "9c5c",
                1
            ],
            [
                "a14f",
                1
            ],
            [
                "639f",
                1
            ]
        ]
    },
    "scenes": {}
}'''
        path = os.path.join(self.test_dir, 'test_zigate.json')
        with open(path, 'w') as fp:
            fp.write(data)
        self.zigate.load_state(path)
        self.assertDictEqual(self.zigate._devices['8ddb'].get_property_value('zone_status'),
                             {'alarm1': False, 'alarm2': False,
                              'tamper': False, 'low_battery': False,
                              'supervision': False, 'restore': False,
                              'trouble': False, 'ac_fault': False,
                              'test_mode': False, 'battery_defect': False}
                             )
        self.assertDictEqual(self.zigate.groups,
                             {'5a92': {('a677', 11), ('9c5c', 1), ('7ad1', 1), ('a14f', 1),
                                       ('d7d0', 1), ('639f', 1), ('fe1b', 1), ('edf0', 1)}}
                             )

    def test_group_membership(self):
        msg_data = b'\x01\x01\x00\x04\x124\x10\x00'
        r = responses.R8062(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertDictEqual(self.zigate.groups,
                             {})

        msg_data = b'\x01\x01\x00\x04\x124\x10\x01\x98v'
        r = responses.R8062(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertDictEqual(self.zigate.groups,
                             {'9876': {('1234', 1)}})

        msg_data = b'\x01\x01\x00\x04\x124\x10\x02\x98v4V'
        r = responses.R8062(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertDictEqual(self.zigate.groups,
                             {'9876': {('1234', 1)},
                              '3456': {('1234', 1)}})

        msg_data = b'\x01\x01\x00\x04\x124\x10\x014V'
        r = responses.R8062(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertDictEqual(self.zigate.groups,
                             {'3456': {('1234', 1)}})

    def test_groups(self):
        self.zigate.add_group('1234', 1, '4567')
        self.assertDictEqual(self.zigate.groups,
                             {'4567': {('1234', 1)},
                              })
        msg_data = b'\x01\x01\x00\x04\x124\x10\x02\x98v4V'
        r = responses.R8062(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertDictEqual(self.zigate.groups,
                             {'9876': {('1234', 1)},
                              '3456': {('1234', 1)}})
        self.zigate.add_group('1234', 1, '4567')
        self.zigate.add_group('0123', 1, '4567')
        self.assertDictEqual(self.zigate.groups,
                             {'9876': {('1234', 1)},
                              '3456': {('1234', 1)},
                              '4567': {('1234', 1), ('0123', 1)},
                              })
        self.zigate.remove_group('1234', 1, '9876')
        self.assertDictEqual(self.zigate.groups,
                             {'3456': {('1234', 1)},
                              '4567': {('1234', 1), ('0123', 1)},
                              })
        self.zigate.remove_group('1234', 1)
        self.assertDictEqual(self.zigate.groups,
                             {'4567': {('0123', 1)},
                              })

        self.assertDictEqual(self.zigate.get_group_for_addr('0123'),
                             {1: ['4567']})

    def test_attribute_discovery(self):
        msg_data = b'\x000\x00\x08\x93-\x03\x03\x00'
        r = responses.R8140(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertCountEqual(self.zigate._devices['932d'].get_attributes(),
                              [{'attribute': 8,
                                'name': 'colour_mode', 'value': None}])

    def test_reporting_request(self):
        device = core.Device()
        self.zigate._devices['1234'] = device
        self.zigate.reporting_request('1234', 3, 0x0300, (0x0000, 0x20))
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'0212340103030000000000010020000000010e10000000'
                         )
        self.zigate.reporting_request('1234', 3, 0x0300, [(0x0000, 0x20)])
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'0212340103030000000000010020000000010e10000000'
                         )
        self.zigate.reporting_request('1234', 3, 0x0300, [(0x0000, 0x20), (0x0001, 0x20)])
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'0212340103030000000000020020000000010e100000000020000100010e10000000'
                         )

    def test_raw_aps_data(self):
        r = self.zigate.raw_aps_data_request('1234', 1, 1, 0x0104, 0x0006, b'payload', 3)
        self.assertEqual(r.sequence, 1)

    def test_assumed_state(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'})
        device.set_attribute(3, 6, {'attribute': 0, 'lqi': 255, 'data': False})
        self.zigate._devices['1234'] = device
        self.zigate.connection.add_auto_response(0x0120, 0x8120, unhexlify(b'01123403000600'))
        r = self.zigate.reporting_request('1234', 3, 6, (0x0000, 0x20))
        self.assertEqual(r.status, 0)
        self.assertFalse(device.assumed_state)
        self.assertDictEqual(device.get_attribute(3, 6, 0),
                             {'attribute': 0, 'data': False, 'name': 'onoff', 'value': False, 'type': bool})
        self.zigate.action_onoff('1234', 3, True)
        self.assertDictEqual(device.get_attribute(3, 6, 0),
                             {'attribute': 0, 'data': False, 'name': 'onoff', 'value': False, 'type': bool})
        self.assertFalse(device.assumed_state)
        self.zigate.connection.add_auto_response(0x0120, 0x8120, unhexlify(b'0112340300068c'))
        r = self.zigate.reporting_request('1234', 3, 6, (0x0000, 0x20))
        self.assertEqual(r.status, 0x8c)
        self.assertTrue(device.assumed_state)
#         self.zigate.action_onoff('1234', 3, 1)
#         self.assertDictEqual(device.get_attribute(3, 6, 0),
#                              {'attribute': 0, 'data': True, 'name': 'onoff', 'value': True, 'type': bool,
#                               'state': 'assumed'})
#         self.zigate.action_onoff('1234', 3, 0)
#         self.assertDictEqual(device.get_attribute(3, 6, 0),
#                              {'attribute': 0, 'data': False, 'name': 'onoff', 'value': False, 'type': bool,
#                               'state': 'assumed'})
#         self.zigate.action_onoff('1234', 3, 2)
#         self.assertDictEqual(device.get_attribute(3, 6, 0),
#                              {'attribute': 0, 'data': True, 'name': 'onoff', 'value': True, 'type': bool,
#                               'state': 'assumed'})
#         self.zigate.action_onoff('1234', 3, 2)
#         self.assertDictEqual(device.get_attribute(3, 6, 0),
#                              {'attribute': 0, 'data': False, 'name': 'onoff', 'value': False, 'type': bool,
#                               'state': 'assumed'})

    def test_handle_response_8085(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'},
                             self.zigate)
        self.zigate._devices['1234'] = device
        msg_data = b'\x01\x01\x00\x08\x02\x124\x01'
        r = responses.R8085(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertEqual(device.get_property_value('remote_level_button'),
                         'down_hold')

    def test_handle_response_8095(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'},
                             self.zigate)
        self.zigate._devices['1234'] = device
        msg_data = b'\x01\x01\x00\x06\x02\x124\x02'
        r = responses.R8095(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertEqual(device.get_property_value('remote_onoff_button'),
                         'middle_click')

    def test_handle_response_80A7(self):
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'},
                             self.zigate)
        self.zigate._devices['1234'] = device
        msg_data = b'\x01\x01\x00\x05\x07\x01\x00\x00\x00\x124'
        r = responses.R80A7(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertEqual(device.get_property_value('remote_scene_button'),
                         'left_click')

    def test_handle_response_8024(self):
        self.zigate._path = None

        def setup_connection():
            self.zigate.connection = transport.FakeTransport()
            self.zigate.connection.add_auto_response(0x0009, 0x8009,
                                                     unhexlify(b'00000123456789abcdef123400000000000000000b'))
            self.zigate.connection.add_auto_response(0x0024, 0x8024,
                                                     unhexlify(b'001234fedcba98765432100b'))
        self.zigate.setup_connection = setup_connection
        self.zigate.autoStart()
        self.assertEqual(self.zigate.addr, '1234')
        self.assertEqual(self.zigate.ieee, 'fedcba9876543210')
        self.assertEqual(self.zigate.channel, 11)

    def test_build_neighbours_table(self):
        cmd = (0x004e, b'000000')
        self.zigate.connection.add_auto_response(cmd, 0x804e,
                                                 unhexlify(b'0100010100abcd0123456789abcdef0123456789abcdef01b616'))
        table = self.zigate.build_neighbours_table()
        self.assertEqual(table, [('0000', 'abcd', 182)])

    def test_build_network_map(self):
        filename = os.path.join(self.test_dir, 'zigate_network.png')
        self.zigate.connection.add_auto_response(0x004e, 0x804e,
                                                 unhexlify(b'0100010100abcd0123456789abcdef0123456789abcdef01b616'))
        self.zigate.build_network_map(self.test_dir)
        self.assertTrue(os.path.exists(filename))

    def test_unsupported_attribute(self):
        # some device like profalux doesn't have model identifier
        device = core.Device({'addr': '1234', 'ieee': '0123456789abcdef'},
                             self.zigate)
        self.zigate._devices['1234'] = device
        r = responses.R8102(unhexlify(b'2f1234010000000586ff0000'), 255)
        r = self.zigate.interpret_response(r)
        self.assertEqual(device.properties,
                         [{'attribute': 5, 'data': 'unsupported', 'name': 'type',
                           'value': 'unsupported', 'type': str}])


if __name__ == '__main__':
    unittest.main()
