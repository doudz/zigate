'''
Created on 22 janv. 2018

@author: sramage
'''
import pyudev
import asyncio
import serial_asyncio
import threading
from functools import partial
import logging
import time


class BaseConnection(object):
    def __init__(self, device):
        loop = device.asyncio_loop
        start_inthread = False
        if not loop:
            loop = asyncio.get_event_loop()
            start_inthread = True
        self.device = device
        coro = self.init_coro(loop)
        loop.run_until_complete(coro)

        if start_inthread:
            self.thread = threading.Thread(target=loop.run_forever)
            self.thread.setDaemon(True)
            self.thread.start()

    def init_coro(self, loop):
        pass

    def _find_port(self, port):
        '''
        automatically discover zigate port if needed
        '''
        port = port or 'auto'
        if port == 'auto':
            self.device._logger.debug('Searching ZiGate port')
            context = pyudev.Context()
            devices = list(context.list_devices(ID_USB_DRIVER='pl2303'))
            if devices:
                port = devices[0].device_node
                self.device._logger.debug('ZiGate found at {}'.format(port))
            else:
                self.device._logger.debug('ZiGate not found')
                raise Exception('ZiGate not found')
        return port

    def send(self, data):
        pass

class SerialConnection(BaseConnection):
    def __init__(self, device, port=None):
        self._port = self._find_port(port)
        BaseConnection.__init__(self, device)

    def init_coro(self, loop):
        ZiGateProtocol.connection = self
        ZiGateProtocol.device = self.device
        coro = serial_asyncio.create_serial_connection(loop, ZiGateProtocol,
                                                       self._port,
                                                       baudrate=115200,
                                                       )
        return coro


class WiFiConnection(BaseConnection):
    def __init__(self, device, host, port=9999):
        self._host = host
        self._port = port
        BaseConnection.__init__(self, device)

    def init_coro(self, loop):
        ZiGateProtocol.connection = self
        ZiGateProtocol.device = self.device
        coro = loop.create_connection(ZiGateProtocol, self._host, self._port)
        return coro


class ZiGateProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        self.transport = None
 
    def connection_made(self, transport):
        self.transport = transport
        self.connection.send = transport.write
 
    def data_received(self, data):
        try:
            self.device.read_data(data)
        except Exception as e:
            logging.debug('ERROR {}'.format(e))
 
    def connection_lost(self, exc):
        pass
