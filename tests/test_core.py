'''
ZiGate core Tests
-------------------------
'''

import unittest
import os
import shutil
import tempfile
from zigate import ZiGate, responses, transport, core
from binascii import hexlify


class TestCore(unittest.TestCase):
    def setUp(self):
        core.WAIT_TIMEOUT = 2 * core.SLEEP_INTERVAL  # reduce timeout during test
        self.zigate = ZiGate(auto_start=False)
        self.zigate.connection = transport.FakeTransport()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

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
                "rssi": 135,
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
                "rssi": 207
            }
        }
        ],
    "groups": {},
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

    def test_attribute_discovery(self):
        msg_data = b'\x000\x00\x08\x93-\x03\x03\x00'
        r = responses.R8140(msg_data, 255)
        self.zigate.interpret_response(r)
        self.assertCountEqual(self.zigate._devices['932d'].get_attributes(),
                              [{'attribute': 8,
                                'name': 'colour_mode', 'value': None}])

    def test_reporting_request(self):
        self.zigate.reporting_request('1234', 3, 0x0300, (0x0000, 0x20))
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'0212340103030000000000010020000000000000000000'
                         )
        self.zigate.reporting_request('1234', 3, 0x0300, [(0x0000, 0x20)])
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'0212340103030000000000010020000000000000000000'
                         )
        self.zigate.reporting_request('1234', 3, 0x0300, [(0x0000, 0x20), (0x0001, 0x20)])
        self.assertEqual(hexlify(self.zigate.connection.get_last_cmd()),
                         b'02123401030300000000000200200000000000000000000020000100000000000000'
                         )



if __name__ == '__main__':
    unittest.main()
