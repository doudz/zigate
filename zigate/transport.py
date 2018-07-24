'''
Created on 22 janv. 2018

@author: sramage
'''
# import pyudev
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
from .const import ZIGATE_PACKET_RECEIVED, ZIGATE_FAILED_TO_CONNECT

LOGGER = logging.getLogger('zigate')


class ZIGATE_NOT_FOUND(Exception):
    pass


class ZIGATE_CANNOT_CONNECT(Exception):
    pass


class ThreadSerialConnection(object):
    def __init__(self, device, port=None):
        self._buffer = b''
        self._port = port
        self.device = device
        self.queue = queue.Queue()
        self._running = True
        self.reconnect()
#         self.serial = self.initSerial()
        self.thread = threading.Thread(target=self.listen)
        self.thread.setDaemon(True)
        self.thread.start()

    def initSerial(self):
        self._port = self._find_port(self._port)
        return serial.Serial(self._port, 115200)

    def reconnect(self):
        delay = 1
        while True:
            try:
                self.serial = self.initSerial()
                break
            except ZIGATE_NOT_FOUND:
                LOGGER.error('ZiGate has not been found, please check configuration.')
                sys.exit(2)
            except:
                msg = 'Failed to connect, retry in {} sec...'.format(delay)
                dispatcher.send(ZIGATE_FAILED_TO_CONNECT, message=msg)
                LOGGER.error(msg)
                time.sleep(delay)
                if delay < 60:
                    delay *= 2
        return self.serial

    def packet_received(self, raw_message):
        dispatcher.send(ZIGATE_PACKET_RECEIVED, packet=raw_message)

    def read_data(self, data):
        '''
        Read ZiGate output and split messages
        '''
        self._buffer += data
#         print(self._buffer)
        endpos = self._buffer.find(b'\x03')
        while endpos != -1:
            startpos = self._buffer.find(b'\x01')
            raw_message = self._buffer[startpos:endpos+1]
#             print(raw_message)
            threading.Thread(target=self.packet_received, args=(raw_message,)).start()
            self._buffer = self._buffer[endpos + 1:]
            endpos = self._buffer.find(b'\x03')

    def listen(self):
        while self._running:
            try:
                data = self.serial.read(self.serial.in_waiting)
            except:
                data = None
                LOGGER.error('OOPS connection lost, reconnect...')
                self.reconnect()
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
            LOGGER.info('Searching ZiGate port')
            devices = list(serial.tools.list_ports.grep('067b:2303'))
            if devices:
                port = devices[0].device
                if len(devices) == 1:
                    LOGGER.info('ZiGate found at {}'.format(port))
                else:
                    LOGGER.warning('Found the following devices')
                    for device in devices:
                        LOGGER.warning('* {0} - {0.manufacturer}'.format(device))
    #                 port = devices[0].device_node
                    LOGGER.warning('Choose the first device... {}'.format(port))
            else:
                LOGGER.error('ZiGate not found')
                raise ZIGATE_NOT_FOUND('ZiGate not found')
        return port

    def is_connected(self):
        return self.serial.isOpen()

    def close(self):
        self._running = False
        while self.thread.is_alive():
            time.sleep(0.1)
        self.serial.close()


class ThreadSocketConnection(ThreadSerialConnection):
    def __init__(self, device, host, port=None):
        self._host = host
        ThreadSerialConnection.__init__(self, device, port)

    def initSerial(self):
        if self._port in (None, 'auto'):
            ports = [23, 9999]
        else:
            ports = [self._port]
        for port in ports:
            try:
                s = socket.create_connection((self._host, port), 10)
                LOGGER.debug('ZiGate found on port {}'.format(port))
                return s
            except:
                LOGGER.debug('ZiGate not found on port {}'.format(port))
                continue
        LOGGER.error('Cannot connect to ZiGate using port {}'.format(self._port))
        raise ZIGATE_CANNOT_CONNECT('Cannot connect to ZiGate using port {}'.format(self._port))

    def listen(self):
        while self._running:
            socket_list = [self.serial]
            read_sockets, write_sockets, error_sockets = select.select(socket_list, socket_list, [])
            if read_sockets:
                data = self.serial.recv(1024)
                if data:
                    self.read_data(data)
                else:
                    LOGGER.error('OOPS connection lost, reconnect...')
                    self.reconnect()
            if write_sockets:
                while not self.queue.empty():
                    data = self.queue.get()
                    self.serial.sendall(data)
            time.sleep(0.05)

    def is_connected(self):  # TODO: check if socket is alive
        return True

