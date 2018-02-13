'''
Created on 22 janv. 2018

@author: sramage
'''
import pyudev
import threading
import logging
import time
import serial
import queue
import socket
from pydispatch import dispatcher

LOGGER = logging.getLogger('zigate')
ZIGATE_PACKET_RECEIVED = 'ZIGATE_PACKET_RECEIVED'


class ThreadSerialConnection(object):
    def __init__(self, device, port=None):
        self._buffer = b''
        self._port = port
        self.device = device
        self.queue = queue.Queue()
        self._running = True
        self.serial = self.initSerial()
        self.thread = threading.Thread(target=self.listen)
        self.thread.setDaemon(True)
        self.thread.start()

    def initSerial(self):
        self._port = self._find_port(self._port)
        return serial.Serial(self._port, 115200)

    def packet_received(self, raw_message):
        dispatcher.send(ZIGATE_PACKET_RECEIVED, packet=raw_message)

    def read_data(self, data):
        '''
        Read ZiGate output and split messages
        '''
        self._buffer += data
        endpos = self._buffer.find(b'\x03')
        while endpos != -1:
            startpos = self._buffer.find(b'\x01')
            raw_message = self._buffer[startpos:endpos+1]
            threading.Thread(target=self.packet_received, args=(raw_message,)).start()
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    def listen(self):
        while self._running:
            data = self.serial.read(self.serial.in_waiting)
            if data:
                self.read_data(data)
            while not self.queue.empty():
                data = self.queue.get()
                self.serial.write(data)
            time.sleep(0.05)

    def send(self, data):
        self.queue.put(data)

    def _find_port(self, port):
        '''
        automatically discover zigate port if needed
        '''
        port = port or 'auto'
        if port == 'auto':
            LOGGER.debug('Searching ZiGate port')
            context = pyudev.Context()
            devices = list(context.list_devices(ID_USB_DRIVER='pl2303'))
            if devices:
                port = devices[0].device_node
                LOGGER.debug('ZiGate found at {}'.format(port))
            else:
                LOGGER.error('ZiGate not found')
                raise Exception('ZiGate not found')
        return port

    def is_connected(self):
        return self.serial.is_open

    def close(self):
        self._running = False
        while self.thread.is_alive():
            time.sleep(0.1)
        self.serial.close()


class ThreadSocketConnection_old(ThreadSerialConnection):
    def __init__(self, device, host, port=9999):
        self._host = host
        ThreadSerialConnection.__init__(self, device, port)

    def initSerial(self):
        return serial.serial_for_url('socket://{}:{}'.format(self._host, self._port))


class ThreadSocketConnection(ThreadSerialConnection):
    def __init__(self, device, host, port=9999):
        self._host = host
        ThreadSerialConnection.__init__(self, device, port)

    def initSerial(self):
        return socket.create_connection((self._host, self._port), timeout=0.05)

    def listen(self):
        while self._running:
            try:
                data = self.serial.recv(1024)
            except socket.timeout:
                data = None
            if data:
                self.read_data(data)
            while not self.queue.empty():
                data = self.queue.get()
                self.serial.sendall(data)
#             time.sleep(0.05)

    def is_connected(self):  # TODO: check if socket is alive
        return True

