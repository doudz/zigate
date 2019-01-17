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
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())

        data = b'\x01123'
        connection.read_data(data)
        self.assertEqual(0, connection.received.qsize())

        data = b'123\x03'
        connection.read_data(data)
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x01123123\x03', connection.received.get())

        data = b'123\x03'
        connection.read_data(data)
        self.assertEqual(0, connection.received.qsize())

        data = b'123\x03\x01123\x03'
        connection.read_data(data)
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())

        data = b'123\x01123\x03'
        connection.read_data(data)
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())

        data = b'\x01123\x03123\x03\x01456\x03\x011'
        connection.read_data(data)
        self.assertEqual(2, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())
        self.assertEqual(b'\x01456\x03', connection.received.get())

        data = b'456'
        connection.read_data(data)
        self.assertEqual(0, connection.received.qsize())

        data = b'123\x03'
        connection.read_data(data)
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x011456123\x03', connection.received.get())

        data = b'\x01123\x01123\x01123\x03'
        connection.read_data(data)
        self.assertEqual(1, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())

        data = b'\x01123\x01123\x01123\x03\x01456\x03'
        connection.read_data(data)
        self.assertEqual(2, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())
        self.assertEqual(b'\x01456\x03', connection.received.get())

        data = b'\x01123\x01123\x01\x01123\x03\x03\x01456\x03'
        connection.read_data(data)
        self.assertEqual(2, connection.received.qsize())
        self.assertEqual(b'\x01123\x03', connection.received.get())
        self.assertEqual(b'\x01456\x03', connection.received.get())

    def test_initial_failed(self):
        success = False
        try:
            connection = transport.ThreadSerialConnection(None, '/dummyport')
        except transport.ZIGATE_CANNOT_CONNECT:
            success = True
        self.assertTrue(success)
        success = False
        try:
            connection = transport.ThreadSocketConnection(None, 'fake.address')
        except transport.ZIGATE_CANNOT_CONNECT:
            success = True
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
