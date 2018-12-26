'''
ZiGate core Tests
-------------------------
'''

import unittest
import os
import tempfile
from zigate import ZiGate, responses, transport


class TestCore(unittest.TestCase):
    def setUp(self):
        self.zigate = ZiGate(auto_start=False)
        self.zigate.connection = transport.FakeTransport()
        self.test_dir = tempfile.mkdtemp()

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
                             {
                              '4567': {('0123', 1)},
                              })


if __name__ == '__main__':
    unittest.main()
