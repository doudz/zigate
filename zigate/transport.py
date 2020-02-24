#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

import threading
import logging
import time
import serial
import serial.tools.list_ports
import queue
import socket
import select
from pydispatch import dispatcher
import sys
from .const import ZIGATE_FAILED_TO_CONNECT
import struct
from binascii import unhexlify, hexlify


LOGGER = logging.getLogger('zigate')


class ZIGATE_NOT_FOUND(Exception):
    pass


class ZIGATE_CANNOT_CONNECT(Exception):
    pass


class BaseTransport(object):
    def __init__(self):
        self._buffer = b''
        self.queue = queue.Queue()
        self.received = queue.Queue()

    def read_data(self, data):
        '''
        Read ZiGate output and split messages
        '''
        LOGGER.debug('Raw packet received, {}'.format(data))
        self._buffer += data
#         print(self._buffer)
        endpos = self._buffer.find(b'\x03')
        while endpos != -1:
            startpos = self._buffer.rfind(b'\x01', 0, endpos)
            if startpos != -1 and startpos < endpos:
                raw_message = self._buffer[startpos:endpos + 1]
                self.received.put(raw_message)
            else:
                LOGGER.error('Malformed packet received, ignore it')
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    def send(self, data):
        self.queue.put(data)

    def is_connected(self):
        pass

    def close(self):
        pass

    def reconnect(self):
        pass

    def vid_pid(self):
        '''
        return idVendor and idProduct
        '''
        return (0, 0)


class FakeTransport(BaseTransport):
    '''
    Fake transport for test
    '''
    def __init__(self):
        BaseTransport.__init__(self)
        self.sent = []
        self.auto_responder = {}
        self.add_auto_response(0x0010, 0x8010, unhexlify(b'000f3ff0'))
        self.add_auto_response(0x0009, 0x8009, unhexlify(b'00000123456789abcdef12340123456789abcdef0b'))
        # by default add a fake xiaomi temp sensor on address abcd
        self.add_auto_response(0x0015, 0x8015, unhexlify(b'01abcd0123456789abcdef00aa'))

    def start_fake_response(self):
        def periodic_response():
            import random
            while True:
                time.sleep(5)
                temp = int(round(random.random() * 40.0, 2) * 100)
                msg = struct.pack('!BHBHHBBHI', 1, int('abcd', 16), 1, 0x0402, 0, 0, 0x22, 4, temp)
                enc_msg = self.create_fake_response(0x8102, msg, random.randint(0, 255))
                self.received.put(enc_msg)
        t = threading.Thread(target=periodic_response)
        t.setDaemon(True)
        t.start()

    def is_connected(self):
        return True

    def send(self, data):
        self.sent.append(data)
        # retrieve cmd
        data = self.zigate_decode(data[1:-1])
        cmd = struct.unpack('!H', data[0:2])[0]
        # reply 0x8000 ok for cmd
        lqi = 255
        value = struct.pack('!BBHB', 0, 1, cmd, lqi)
        length = len(value)
        checksum = self.checksum(struct.pack('!H', 0x8000),
                                 struct.pack('!B', length),
                                 value)
        raw_message = struct.pack('!HHB{}s'.format(len(value)), 0x8000, length, checksum, value)
        enc_msg = self.zigate_encode(raw_message)
        enc_msg.insert(0, 0x01)
        enc_msg.append(0x03)
        enc_msg = bytes(enc_msg)
        self.received.put(enc_msg)

        data = hexlify(data[5:])
        if (cmd, data) in self.auto_responder:
            self.received.put(self.auto_responder[(cmd, data)])
        elif (cmd, None) in self.auto_responder:
            self.received.put(self.auto_responder[(cmd, None)])

    def add_auto_response(self, cmd, resp, value, lqi=255):
        enc_msg = self.create_fake_response(resp, value, lqi)
        if not isinstance(cmd, tuple):
            cmd = (cmd, None)
        self.auto_responder[cmd] = enc_msg

    def create_fake_response(self, resp, value, lqi=255):
        value += struct.pack('!B', lqi)
        length = len(value)
        checksum = self.checksum(struct.pack('!H', resp),
                                 struct.pack('!B', length),
                                 value)
        raw_message = struct.pack('!HHB{}s'.format(len(value)), resp, length, checksum, value)
        enc_msg = self.zigate_encode(raw_message)
        enc_msg.insert(0, 0x01)
        enc_msg.append(0x03)
        enc_msg = bytes(enc_msg)
        return enc_msg

    def checksum(self, *args):
        chcksum = 0
        for arg in args:
            if isinstance(arg, int):
                chcksum ^= arg
                continue
            for x in arg:
                chcksum ^= x
        return chcksum

    def zigate_encode(self, data):
        encoded = bytearray()
        for b in data:
            if b < 0x10:
                encoded.extend([0x02, 0x10 ^ b])
            else:
                encoded.append(b)
        return encoded

    def zigate_decode(self, data):
        flip = False
        decoded = bytearray()
        for b in data:
            if flip:
                flip = False
                decoded.append(b ^ 0x10)
            elif b == 0x02:
                flip = True
            else:
                decoded.append(b)
        return decoded

    def get_last_cmd(self):
        if not self.sent:
            return
        cmd = self.sent[-1]
        data = self.zigate_decode(cmd[1:-1])[5:]
        return data


class ThreadSerialConnection(BaseTransport):
    def __init__(self, device, port=None, search_re='ZiGate|067b:2303|CP2102'):
        BaseTransport.__init__(self)
        self._port = port
        self.device = device
        self.serial = None
        self._search_re = search_re
        self._running = True
        self.reconnect(False)
        self.thread = threading.Thread(target=self.listen,
                                       name='ZiGate-Listen')
        self.thread.setDaemon(True)
        self.thread.start()

    def initSerial(self):
        self._port = self._find_port(self._port)
        return serial.Serial(self._port, 115200)

    def vid_pid(self):
        if self.serial:
            ports = list(serial.tools.list_ports.grep(self.serial.port))
            if ports:
                return (ports[0].vid, ports[0].pid)
        return BaseTransport.vid_pid(self)

    def reconnect(self, retry=True):
        delay = 1
        while self._running:
            try:
                if self.serial:
                    self.serial.close()  # just to be sure it's not already open
                self.serial = self.initSerial()
                break
            except ZIGATE_NOT_FOUND:
                LOGGER.error('ZiGate has not been found, please check configuration.')
                if not retry:
                    sys.exit(2)
            except Exception:
                if not retry:
                    LOGGER.error('Cannot connect to ZiGate using port {}'.format(self._port))
                    raise ZIGATE_CANNOT_CONNECT('Cannot connect to ZiGate using port {}'.format(self._port))
                    sys.exit(2)
                # maybe port has change so try to find it
                if delay > 3:
                    self._port = 'auto'
            msg = 'Failed to connect, retry in {} sec...'.format(int(delay))
            dispatcher.send(ZIGATE_FAILED_TO_CONNECT, message=msg)
            LOGGER.error(msg)
            time.sleep(int(delay))
            if delay < 30:
                delay *= 1.5

    def listen(self):
        while self._running:
            try:
                data = self.serial.read(self.serial.in_waiting)
            except Exception:
                data = None
                LOGGER.error('OOPS connection lost, reconnect...')
                self.reconnect()
            if data:
                self.read_data(data)
            while not self.queue.empty():
                data = self.queue.get()
                self.serial.write(data)
            time.sleep(0.05)

    def _find_port(self, port):
        '''
        automatically discover zigate port if needed
        '''
        return discover_port(port, self._search_re)

    def is_connected(self):
        return self.serial.isOpen()

    def close(self):
        self._running = False
        tries = 0
        while self.thread.is_alive():
            tries += 1
            if tries > 50:
                break
            time.sleep(0.1)
        self.serial.close()


class ThreadSocketConnection(ThreadSerialConnection):
    def __init__(self, device, host, port=None):
        self._host = host
        self._is_connected = False
        ThreadSerialConnection.__init__(self, device, port)

    def initSerial(self):
        if self._port in (None, 'auto'):
            ports = [23, 9999]
        else:
            ports = [self._port]
        host = self._find_host(self._host)
        for port in ports:
            try:
                s = socket.create_connection((host, port))
                LOGGER.debug('ZiGate found on {} port {}'.format(host, port))
                self._is_connected = True
                return s
            except Exception:
                LOGGER.debug('ZiGate not found on {} port {}'.format(host, port))
                continue
        LOGGER.error('Cannot connect to ZiGate using {} port {}'.format(self._host, self._port))
        raise ZIGATE_CANNOT_CONNECT('Cannot connect to ZiGate using {} port {}'.format(self._host, self._port))

    def _find_host(self, host):
        host = host or 'auto'
        if host == 'auto':
            LOGGER.info('Searching ZiGate Wifi host')
            host = discover_host()
            if not host:
                LOGGER.error('ZiGate not found')
#                 raise ZIGATE_NOT_FOUND('ZiGate not found')
        return host

    def reconnect(self, retry=True):
        self._is_connected = False
        if self.serial:
            try:
                self.serial.shutdown(2)
            except Exception:
                pass
        ThreadSerialConnection.reconnect(self, retry=retry)

    def listen(self):
        while self._running:
            socket_list = [self.serial]
            read_sockets, write_sockets, error_sockets = select.select(socket_list, socket_list, [], 5)
            if read_sockets:
                data = self.serial.recv(1024)
                if data:
                    self.read_data(data)
                else:
                    LOGGER.warning('OOPS connection lost, reconnect...')
                    self.reconnect()
            if write_sockets:
                while not self.queue.empty():
                    data = self.queue.get()
                    try:
                        self.serial.send(data)
                    except OSError:
                        LOGGER.warning('OOPS connection lost, reconnect...')
                        self.reconnect()
            time.sleep(0.05)

    def is_connected(self):
        return self._is_connected

    def close(self):
        self._running = False
        tries = 0
        while self.thread.is_alive():
            tries += 1
            if tries > 50:
                break
            time.sleep(0.1)
        self.serial.shutdown(2)
        self.serial.close()

    def vid_pid(self):
        '''
        return idVendor and idProduct
        '''
        return (0, 0)


def discover_port(port='auto', search_re='ZiGate|067b:2303|CP2102'):
    '''
    automatically discover zigate port if needed
    '''
    port = port or 'auto'
    if port == 'auto':
        LOGGER.info('Searching ZiGate port')
        devices = list(serial.tools.list_ports.grep(search_re))
        if devices:
            port = devices[0].device
            if len(devices) == 1:
                LOGGER.info('ZiGate found at {}'.format(port))
            else:
                LOGGER.warning('Found the following devices')
                for device in devices:
                    LOGGER.warning('* {0} - {0.manufacturer}'.format(device))
                LOGGER.warning('Choose the first device... {}'.format(port))
        else:
            LOGGER.error('ZiGate not found')
            raise ZIGATE_NOT_FOUND('ZiGate not found')
    return port


def discover_host():
    """
    Automatically discover WiFi ZiGate using zeroconf
    only compatible with WiFi firmware 2.x
    """
    from zeroconf import ServiceBrowser, Zeroconf
    host = None

    def on_service_state_change(zeroconf, service_type, name, state_change):
        pass

    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_zigate._tcp.local.",
                             handlers=[on_service_state_change])
    i = 0
    while not host:
        time.sleep(0.1)
        if browser.services:
            service = list(browser.services.values())[0]
            info = zeroconf.get_service_info(service.name, service.alias)
            host = socket.inet_ntoa(info.address)
        i += 1
        if i > 50:
            break
    zeroconf.close()
    return host
