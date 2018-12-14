'''
ZiGate Transport Tests
-------------------------
'''

import unittest
from zigate import transport


class TestTransport(unittest.TestCase):
    def test_packet(self):
        connection = transport.BaseTransport()
        data = b'\x01123\x03'
        connection.read_data(data)
        self.assertEqual(data, connection.received.get())
        print(connection._buffer)
        data = b'123\x03'
        connection.read_data(data)
#         self.assertEqual(data, connection.received.get())
        print(connection._buffer)
        data = b'\x01123'
        connection.read_data(data)
#         self.assertEqual(data, connection.received.get())
        print(connection._buffer)
        data = b'123\x01123\x03'
        connection.read_data(data)
#         self.assertEqual(data, connection.received.get())
        print(connection._buffer)
        data = b'123\x03123456'
        connection.read_data(data)
#         self.assertEqual(data, connection.received.get())
        print(connection._buffer)
        data = b'456'
        connection.read_data(data)
#         self.assertEqual(data, connection.received.get())
        print(connection._buffer)


if __name__ == '__main__':
    unittest.main()
