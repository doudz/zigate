#! /usr/bin/python3
from binascii import (hexlify, unhexlify)
import traceback
from time import (sleep, strftime, time)
from collections import OrderedDict
import logging
import json
import os
from pydispatch import dispatcher
from .transport import (ThreadSerialConnection, ThreadSocketConnection)
from .responses import (RESPONSES, Response)
from .const import *
from .clusters import (CLUSTERS, Cluster, get_cluster)
import functools
import struct
import threading
import random
from enum import Enum
import colorsys
import queue


LOGGER = logging.getLogger('zigate')


AUTO_SAVE = 5*60  # 5 minutes
BIND_REPORT_LIGHT = True  # automatically bind and report state for light
SLEEP_INTERVAL = 0.2
ACTIONS = {}

# Device id
ACTUATORS = [0x0010, 0x0051,
             0x010a,
             0x0100, 0x0101, 0x0102, 0x0103, 0x0105, 0x0110,
             0x0200, 0x0210, 0x0220]
#             On/off light 0x0000
#             On/off plug-in unit 0x0010
#             Dimmable light 0x0100
#             Dimmable plug-in unit 0x0110
#             Color light 0x0200
#             Extended color light 0x0210
#             Color temperature light 0x0220


def register_actions(action):
    def decorator(func):
        if action not in ACTIONS:
            ACTIONS[action] = []
        ACTIONS[action].append(func.__name__)
        return func
    return decorator


class AddrMode(Enum):
    bound = 0
    group = 1
    short = 2
    ieee = 3


def hex_to_rgb(h):
    ''' convert hex color to rgb tuple '''
    h = h.strip('#')
    return tuple(int(h[i:i+2], 16)/255 for i in (0, 2 ,4))


def rgb_to_xy(rgb):
    ''' convert rgb tuple to xy tuple '''
    red, green, blue = rgb
    r = ((red + 0.055) / (1.0 + 0.055))**2.4 if (red > 0.04045) else (red / 12.92)
    g = ((green + 0.055) / (1.0 + 0.055))**2.4 if (green > 0.04045) else (green / 12.92)
    b = ((blue + 0.055) / (1.0 + 0.055))**2.4 if (blue > 0.04045) else (blue / 12.92)
    X = r * 0.664511 + g * 0.154324 + b * 0.162028
    Y = r * 0.283881 + g * 0.668433 + b * 0.047685
    Z = r * 0.000088 + g * 0.072310 + b * 0.986039
    cx = 0
    cy = 0
    if (X + Y + Z) != 0:
        cx = X / (X + Y + Z)
        cy = Y / (X + Y + Z)
    return (cx, cy)


def hex_to_xy(h):
    ''' convert hex color to xy tuple '''
    return rgb_to_xy(hex_to_rgb(h))


def dispatch_signal(signal=dispatcher.Any, sender=dispatcher.Anonymous,
                    *arguments, **named):
    '''
    Dispatch signal with exception proof
    '''
    LOGGER.debug('Dispatch {}'.format(signal))
    try:
        dispatcher.send(signal, sender, *arguments, **named)
    except Exception:
        LOGGER.error('Exception dispatching signal {}'.format(signal))
        LOGGER.error(traceback.format_exc())


class ZiGate(object):

    def __init__(self, port='auto', path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True):
        self._devices = {}
        self._groups = {}
        self._path = path
        self._version = None
        self._port = port
        self._last_response = {}  # response to last command type
        self._last_status = {}  # status to last command type
        self._save_lock = threading.Lock()
        self._autosavetimer = None
        self._closing = False
        self.connection = None

        self._addr = None
        self._ieee = None
        self._started = False

        self._packets = queue.Queue()
        self._event_thread = threading.Thread(target=self._event_loop)
        self._event_thread.setDaemon(True)
        self._event_thread.start()

        dispatcher.connect(self._packet_received, ZIGATE_PACKET_RECEIVED)
        dispatcher.connect(self.interpret_response, ZIGATE_RESPONSE_RECEIVED)
#         dispatcher.connect(self.decode_data, ZIGATE_PACKET_RECEIVED)
        if auto_start:
            self.autoStart()
            if auto_save:
                self.start_auto_save()

    def _event_loop(self):
        while True:
            if not self._packets.empty():
                packet = self._packets.get()
                self.decode_data(packet)
            sleep(SLEEP_INTERVAL)

    def _packet_received(self, packet):
        self._packets.put(packet)

    def setup_connection(self):
        self.connection = ThreadSerialConnection(self, self._port)

    def close(self):
        self._closing = True
        if self._autosavetimer:
            self._autosavetimer.cancel()
        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            LOGGER.error('Exception during closing')
            LOGGER.error(traceback.format_exc())
        self._started = False

    def save_state(self, path=None):
        self._save_lock.acquire()
        path = path or self._path
        self._path = os.path.expanduser(path)
        try:
            data = {'devices': list(self._devices.values()),
                    'groups': self._groups
                    }
            with open(self._path, 'w') as fp:
                json.dump(data, fp, cls=DeviceEncoder,
                          sort_keys=True, indent=4, separators=(',', ': '))
        except Exception:
            LOGGER.error('Failed to save persistent file {}'.format(self._path))
            LOGGER.error(traceback.format_exc())
        self._save_lock.release()

    def load_state(self, path=None):
        LOGGER.debug('Try loading persistent file')
        path = path or self._path
        self._path = os.path.expanduser(path)
        if os.path.exists(self._path):
            try:
                with open(self._path) as fp:
                    data = json.load(fp)
                if not isinstance(data, dict):  # old version
                    data = {'devices': data, 'groups': {}}
                self._groups = data.get('groups', {})
                devices = data.get('devices', [])
                for data in devices:
                    device = Device.from_json(data, self)
                    self._devices[device.addr] = device
                    device._create_actions()
                LOGGER.debug('Load success')
                return True
            except Exception:
                LOGGER.error('Failed to load persistent file {}'.format(self._path))
                LOGGER.error(traceback.format_exc())
        LOGGER.debug('No file to load')
        return False

    def start_auto_save(self):
        LOGGER.debug('Auto saving {}'.format(self._path))
        self.save_state()
        self._autosavetimer = threading.Timer(AUTO_SAVE, self.start_auto_save)
        self._autosavetimer.setDaemon(True)
        self._autosavetimer.start()

    def __del__(self):
        self.close()

    def autoStart(self):
        '''
        Auto Start sequence:
            - Load persistent file
            - setup connection
            - Set Channel mask
            - Set Type Coordinator
            - Start Network
            - Refresh devices list
        '''
        if self._started:
            return
        self.load_state()
        self.setup_connection()
        self.get_version()
#         erase = not self.load_state()
#         if erase:
#             self.erase_persistent()
        self.set_channel()
        self.set_type(TYPE_COORDINATOR)
        LOGGER.debug('Check network state')
        self.start_network()
        network_state = self.get_network_state()
        if not network_state:
            LOGGER.error('Failed to get network state')
        if not network_state or network_state.get('extend_pan') == 0:
            LOGGER.debug('Network is down, start it')
            self.start_network(True)
        self.get_devices_list(True)
        self.need_refresh()
#         for device in self.devices:
#             device._bind_report()

    def need_refresh(self):
        '''
        scan device which need refresh
        auto refresh if possible
        else dispatch signal
        '''
        for device in self.devices:
            if device.need_refresh():
                if device.receiver_on_when_idle():
                    LOGGER.debug('Auto refresh device {}'.format(device))
                    device.refresh_device()
                else:
                    dispatch_signal(ZIGATE_DEVICE_NEED_REFRESH,
                                    self, **{'zigate': self,
                                             'device': device})

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

    def checksum(self, *args):
        chcksum = 0
        for arg in args:
            if isinstance(arg, int):
                chcksum ^= arg
                continue
            for x in arg:
                chcksum ^= x
        return chcksum

    def send_to_transport(self, data):
        if not self.connection.is_connected():
            raise Exception('Not connected to zigate')
        self.connection.send(data)

    def send_data(self, cmd, data="", wait_response=None):
        '''
        send data through ZiGate
        '''
        LOGGER.debug('REQUEST : 0x{:04x} {}'.format(cmd, data))
        self._last_status[cmd] = None
        if wait_response:
            self._clear_response(wait_response)
        if isinstance(cmd, int):
            byte_cmd = struct.pack('!H', cmd)
        elif isinstance(data, str):
            byte_cmd = bytes.fromhex(cmd)
        else:
            byte_cmd = cmd
        if isinstance(data, str):
            byte_data = bytes.fromhex(data)
        else:
            byte_data = data
        assert type(byte_cmd) == bytes
        assert type(byte_data) == bytes
        length = len(byte_data)
        byte_length = struct.pack('!H', length)
        checksum = self.checksum(byte_cmd, byte_length, byte_data)

        msg = struct.pack('!HHB%ds' % length, cmd, length, checksum, byte_data)
        LOGGER.debug('Msg to send {}'.format(hexlify(msg)))

        enc_msg = self.zigate_encode(msg)
        enc_msg.insert(0, 0x01)
        enc_msg.append(0x03)
        encoded_output = bytes(enc_msg)
        LOGGER.debug('Encoded Msg to send {}'.format(encoded_output))

        self.send_to_transport(encoded_output)
        status = self._wait_status(cmd)
        if wait_response and status is not None:
            r = self._wait_response(wait_response)
            return r
        return status

    def decode_data(self, packet):
        '''
        Decode raw packet message
        '''
        decoded = self.zigate_decode(packet[1:-1])
        msg_type, length, checksum, value, rssi = \
            struct.unpack('!HHB%dsB' % (len(decoded) - 6), decoded)
        if length != len(value)+1:  # add rssi length
            LOGGER.error('Bad length {} != {} : {}'.format(length,
                                                           len(value)+1,
                                                           value))
            return
        computed_checksum = self.checksum(decoded[:4], rssi, value)
        if checksum != computed_checksum:
            LOGGER.error('Bad checksum {} != {}'.format(checksum,
                                                        computed_checksum))
            return
        response = RESPONSES.get(msg_type, Response)(value, rssi)
        if msg_type != response.msg:
            LOGGER.warning('Unknown response 0x{:04x}'.format(msg_type))
        LOGGER.debug(response)
        self._last_response[msg_type] = response
        dispatch_signal(ZIGATE_RESPONSE_RECEIVED, self, response=response)

    def interpret_response(self, response):
        if response.msg == 0x8000:  # status
            if response['status'] != 0:
                LOGGER.error('Command 0x{:04x} failed {} : {}'.format(response['packet_type'],
                                                                 response.status_text(),
                                                                 response['error']))
            self._last_status[response['packet_type']] = response['status']
        elif response.msg == 0x8015:  # device list
            keys = set(self._devices.keys())
            known_addr = set([d['addr'] for d in response['devices']])
            LOGGER.debug('Known devices in zigate : {}'.format(known_addr))
            missing = keys.difference(known_addr)
            LOGGER.debug('Previous devices missing : {}'.format(missing))
            for addr in missing:
                self._tag_missing(addr)
#                 self._remove_device(addr)
            for d in response['devices']:
                device = Device(dict(d), self)
                self._set_device(device)
        elif response.msg == 0x8042:  # node descriptor
            addr = response['addr']
            d = self.get_device_from_addr(addr)
            if d:
                d.update_info(response.cleaned_data())
        elif response.msg == 0x8043:  # simple descriptor
            addr = response['addr']
            endpoint = response['endpoint']
            d = self.get_device_from_addr(addr)
            if d:
                ep = d.get_endpoint(endpoint)
                ep.update(response.cleaned_data())
                ep['in_clusters'] = response['in_clusters']
                ep['out_clusters'] = response['out_clusters']
                d._create_actions()
                d._bind_report(endpoint)
                # ask for various general information
                for c in response['in_clusters']:
                    cluster = CLUSTERS.get(c)
                    if cluster:
                        self.read_attribute_request(addr, endpoint, c,
                                                    list(cluster.attributes_def.keys()))
        elif response.msg == 0x8045:  # endpoint list
            addr = response['addr']
            for endpoint in response['endpoints']:
                self.simple_descriptor_request(addr, endpoint['endpoint'])
        elif response.msg == 0x8048:  # leave
            device = self.get_device_from_ieee(response['ieee'])
            if device:
                self._remove_device(device.addr)
        elif response.msg in (0x8100, 0x8102, 0x8110, 0x8401):  # attribute report or IAS Zone status change
            if response['status'] != 0:
                LOGGER.debug('Receive Bad status')
                return
            device = self._get_device(response['addr'])
            device.rssi = response['rssi']
            r = device.set_attribute(response['endpoint'],
                                     response['cluster'],
                                     response.cleaned_data())
            if r is None:
                return
            added, attribute_id = r
            changed = device.get_attribute(response['endpoint'],
                                           response['cluster'],
                                           attribute_id, True)
            if added:
                dispatch_signal(ZIGATE_ATTRIBUTE_ADDED, self, **{'zigate': self,
                                                                 'device': device,
                                                                 'attribute': changed})
            else:
                dispatch_signal(ZIGATE_ATTRIBUTE_UPDATED, self, **{'zigate': self,
                                                                   'device': device,
                                                                   'attribute': changed})
        elif response.msg == 0x004D:  # device announce
            LOGGER.debug('Device Announce')
            device = Device(response.data, self)
            self._set_device(device)
#         else:
#             LOGGER.debug('Do nothing special for response {}'.format(response))

    def _get_device(self, addr):
        '''
        get device from addr
        create it if necessary
        '''
        d = self.get_device_from_addr(addr)
        if not d:
            LOGGER.warning('Device not found, create it (this isn\'t normal)')
            d = Device({'addr': addr}, self)
            self._set_device(d)
            self.get_devices_list()  # since device is missing, request info
        return d

    def _tag_missing(self, addr):
        '''
        tag a device as missing
        '''
        if addr in self._devices:
            self._devices[addr].missing = True
            LOGGER.warning('The device {} is missing'.format(addr))
            dispatch_signal(ZIGATE_DEVICE_UPDATED,
                            self, **{'zigate': self,
                                     'device': self._devices[addr]})

    def get_missing(self):
        '''
        return missing devices
        '''
        return [device for device in self._devices.values() if device.missing]

    def cleanup_devices(self):
        '''
        remove devices tagged missing
        '''
        to_remove = [device.addr for device in self.get_missing()]
        for addr in to_remove:
            self._remove_device(addr)

    def _remove_device(self, addr):
        '''
        remove device from addr
        '''
        del self._devices[addr]
        dispatch_signal(ZIGATE_DEVICE_REMOVED, **{'zigate': self,
                                                  'addr': addr})

    def _set_device(self, device):
        '''
        add/update device to cache list
        '''
        assert type(device) == Device
        if device.addr in self._devices:
            self._devices[device.addr].update(device)
            dispatch_signal(ZIGATE_DEVICE_UPDATED, self, **{'zigate': self,
                                                            'device':self._devices[device.addr]})
        else:
            # check if device already exist with other address
            d = self.get_device_from_ieee(device.ieee)
            if d:
                LOGGER.warning('Device already exists with another addr {}, removing it.'.format(d.addr))
                self._remove_device(d.addr)
            self._devices[device.addr] = device
            dispatch_signal(ZIGATE_DEVICE_ADDED, self, **{'zigate': self,
                                                          'device': device})
            self.refresh_device(device.addr)

    def get_status_text(self, status_code):
        return STATUS_CODES.get(status_code,
                                'Failed with event code: {}'.format(status_code))

    def _clear_response(self, msg_type):
        if msg_type in self._last_response:
            del self._last_response[msg_type]

    def _wait_response(self, msg_type):
        '''
        wait for next msg_type response
        '''
        LOGGER.debug('Waiting for message 0x{:04x}'.format(msg_type))
        t1 = time()
        while self._last_response.get(msg_type) is None:
            sleep(0.01)
            t2 = time()
            if t2-t1 > 3:  # no response timeout
                LOGGER.error('No response waiting command 0x{:04x}'.format(msg_type))
                return
        LOGGER.debug('Stop waiting, got message 0x{:04x}'.format(msg_type))
        return self._last_response.get(msg_type)

    def _wait_status(self, cmd):
        '''
        wait for status of cmd
        '''
        LOGGER.debug('Waiting for status message for command 0x{:04x}'.format(cmd))
        t1 = time()
        while self._last_status.get(cmd) is None:
            sleep(0.01)
            t2 = time()
            if t2-t1 > 3:  # no response timeout
                LOGGER.error('No response after command 0x{:04x}'.format(cmd))
                return
        LOGGER.debug('STATUS code to command 0x{:04x}:{}'.format(cmd, self._last_status.get(cmd)))
        return self._last_status.get(cmd)

    def __addr(self, addr):
        ''' convert hex string addr to int '''
        if isinstance(addr, str):
            addr = int(addr, 16)
        return addr

    def __haddr(self, int_addr, length=4):
        ''' convert int addr to hex '''
        return '{0:0{1}x}'.format(int_addr, length)

    @property
    def ieee(self):
        if not self._ieee:
            self.get_network_state()
        return self._ieee

    @property
    def addr(self):
        if not self._addr:
            self.get_network_state()
        return self._addr

    @property
    def devices(self):
        return list(self._devices.values())

    def get_device_from_addr(self, addr):
        return self._devices.get(addr)

    def get_device_from_ieee(self, ieee):
        if ieee:
            for d in self._devices.values():
                if d.ieee == ieee:
                    return d

    def get_devices_list(self, wait=False):
        '''
        refresh device list from zigate
        '''
        wait_response = None
        if wait:
            wait_response = 0x8015
        self.send_data(0x0015, wait_response=wait_response)

    def get_version(self, refresh=False):
        '''
        get zigate firmware version
        '''
        if not self._version or refresh:
            self._version = self.send_data(0x0010, wait_response=0x8010).data
        return self._version

    def get_version_text(self, refresh=False):
        '''
        get zigate firmware version as text
        '''
        v = self.get_version(refresh)['version']
        return v

    def reset(self):
        '''
        reset zigate
        '''
        return self.send_data(0x0011)

    def erase_persistent(self):
        '''
        erase persistent data in zigate
        '''
        return self.send_data(0x0012)
        # todo, erase local persistent

    def is_permitting_join(self):
        '''
        check if zigate is permitting join
        '''
        r = self.send_data(0x0014, wait_response=0x8014)
        if r:
            r = r.get('status', False)
        return r

    def permit_join(self, duration=30):
        '''
        start permit join
        duration in secs, 0 means stop permit join
        '''
        return self.send_data(0x0049, 'FFFC{:02X}00'.format(duration))

    def stop_permit_join(self):
        '''
        convenient function to stop permit_join
        '''
        return self.permit_join(0)

    def set_channel(self, channels=None):
        '''
        set channel
        '''
        channels = channels or [11, 14, 15, 19, 20, 24, 25]
        if not isinstance(channels, list):
            channels = [channels]
        mask = functools.reduce(lambda acc, x: acc ^ 2 ** x, channels, 0)
        mask = struct.pack('!I', mask)
        return self.send_data(0x0021, mask)

    def set_type(self, typ=TYPE_COORDINATOR):
        '''
        set zigate mode type
        '''
        data = struct.pack('!B', typ)
        self.send_data(0x0023, data)

    def get_network_state(self):
        ''' get network state '''
        r = self.send_data(0x0009, wait_response=0x8009)
        if r:
            data = r.cleaned_data()
            self._addr = data['addr']
            self._ieee = data['ieee']
            return data

    def start_network(self, wait=False):
        ''' start network '''
        wait_response = None
        if wait:
            wait_response = 0x8024
        return self.send_data(0x0024, wait_response=wait_response)

    def start_network_scan(self):
        ''' start network scan '''
        return self.send_data(0x0025)

    def remove_device(self, addr):
        ''' remove device '''
        if addr in self._devices:
            ieee = self._devices[addr]['ieee']
            addr = self.__addr(addr)
            ieee = self.__addr(ieee)
#             data = struct.pack('!QQ', addr, ieee)
            data = struct.pack('!QQ', ieee, ieee)
            return self.send_data(0x0026, data)

    def _bind_unbind(self, cmd, ieee, endpoint, cluster,
                     dst_addr=None, dst_endpoint=1):
        '''
        bind
        if dst_addr not specified, supposed zigate
        '''
        if not dst_addr:
            dst_addr = self.ieee
        if len(dst_addr) == 4:
            if dst_addr in self._groups:
                dst_addr_mode = 1  # AddrMode.group
            elif dst_addr in self._devices:
                dst_addr_mode = 2  # AddrMode.short
            else:
                dst_addr_mode = 0  # AddrMode.bound
            dst_addr_fmt = 'H'
        else:
            dst_addr_mode = 3  # AddrMode.ieee
            dst_addr_fmt = 'Q'
        ieee = self.__addr(ieee)
        dst_addr = self.__addr(dst_addr)
        data = struct.pack('!QBHB'+dst_addr_fmt+'B', ieee, endpoint,
                           cluster, dst_addr_mode, dst_addr, dst_endpoint)
        wait_response = cmd + 0x8000
        return self.send_data(cmd, data, wait_response)

    def bind(self, ieee, endpoint, cluster, dst_addr=None, dst_endpoint=1):
        '''
        bind
        if dst_addr not specified, supposed zigate
        '''
        return self._bind_unbind(0x0030, ieee, endpoint, cluster,
                                 dst_addr, dst_endpoint)

    def bind_addr(self, addr, endpoint, cluster, dst_addr=None,
                  dst_endpoint=1):
        '''
        bind using addr
        if dst_addr not specified, supposed zigate
        convenient function to use addr instead of ieee
        '''
        if addr in self._devices:
            ieee = self._devices[addr]['ieee']
            return self.bind(ieee, endpoint, cluster, dst_addr, dst_endpoint)
        LOGGER.error('Failed to bind, addr {} unknown'.format(addr))

    def unbind(self, ieee, endpoint, cluster, dst_addr=None, dst_endpoint=1):
        '''
        unbind
        if dst_addr not specified, supposed zigate
        '''
        return self._bind_unbind(0x0031, ieee, endpoint, cluster,
                                 dst_addr, dst_endpoint)

    def unbind_addr(self, addr, endpoint, cluster, dst_addr='0000',
                    dst_endpoint=1):
        '''
        unbind using addr
        if dst_addr not specified, supposed zigate
        convenient function to use addr instead of ieee
        '''
        if addr in self._devices:
            ieee = self._devices[addr]['ieee']
            return self.unbind(ieee, endpoint, cluster, dst_addr, dst_endpoint)
        LOGGER.error('Failed to bind, addr {} unknown'.format(addr))

    def node_descriptor_request(self, addr):
        ''' node descriptor request '''
        return self.send_data(0x0042, addr)

    def simple_descriptor_request(self, addr, endpoint):
        '''
        simple_descriptor_request
        '''
        addr = self.__addr(addr)
        data = struct.pack('!HB', addr, endpoint)
        return self.send_data(0x0043, data)

    def power_descriptor_request(self, addr):
        '''
        power descriptor request
        '''
        return self.send_data(0x0044, addr)

    def active_endpoint_request(self, addr):
        '''
        active endpoint request
        '''
        return self.send_data(0x0045, addr)

    def leave_request(self, addr, ieee=None, rejoin=0,
                      remove_children=0):
        '''
        Management Leave request
        rejoin : 0 do not rejoin, 1 rejoin
        remove_children : 0 Leave, removing children,
                            1 = Leave, do not remove children
        '''
        addr = self.__addr(addr)
        if not ieee:
            ieee = self._devices[addr]['ieee']
        ieee = self.__addr(ieee)
        data = struct.pack('!HQBB', addr, ieee, rejoin, remove_children)
        return self.send_data(0x0047, data)

    def lqi_request(self, addr='0000', index=0):
        '''
        Management LQI request
        '''
        addr = self.__addr(addr)
        data = struct.pack('!HB', addr, index)
        return self.send_data(0x004e, data)

    def refresh_device(self, addr):
        '''
        convenient function to refresh device info by calling
        node descriptor
        power descriptor
        active endpoint request
        '''
        self.node_descriptor_request(addr)
#         self.power_descriptor_request(addr)
        self.active_endpoint_request(addr)

    def _generate_addr(self):
        addr = None
        while not addr or addr in self._devices:
            addr = random.randint(1, 0xffff)
        return addr

    @property
    def groups(self):
        '''
        return known groups
        '''
        return self._groups

    def _add_group(self, cmd, addr, endpoint, group=None):
        '''
        Add group
        if group addr not specified, generate one
        return group addr
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        if not group:
            group = self._generate_addr()
        else:
            group = self.__addr(group)
        src_endpoint = 1
        data = struct.pack('!BHBBH', addr_mode, addr,
                           src_endpoint, endpoint, group)
        r = self.send_data(cmd, data)
        group_addr = self.__haddr(group)
        if r == 0:
            if group_addr not in self._groups:
                self._groups[group_addr] = set()
            self._groups[group_addr].add((self.__haddr(addr), endpoint))
        return group_addr

    def add_group(self, addr, endpoint, group=None):
        '''
        Add group
        if group addr not specified, generate one
        return group addr
        '''
        return self._add_group(0x0060, addr, endpoint, group)

    def add_group_identify(self, addr, endpoint, group=None):
        '''
        Add group if identify ??
        if group addr not specified, generate one
        return group addr
        '''
        return self._add_group(0x0065, addr, endpoint, group)

    def view_group(self, addr, endpoint, group):
        '''
        View group
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        group = self.__addr(group)
        src_endpoint = 1
        data = struct.pack('!BHBBH', addr_mode, addr,
                           src_endpoint, endpoint, group)
        return self.send_data(0x0061, data)

    def get_group_membership(self, addr, endpoint, groups):
        '''
        Get group membership
        groups is list of group addr
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        src_endpoint = 1
        length = len(groups)
        groups = [self.__addr(group) for group in groups]
        data = struct.pack('!BHBBB{}H'.format(length), addr_mode, addr,
                           src_endpoint, endpoint, length, *groups)
        return self.send_data(0x0061, data)

    def remove_group(self, addr, endpoint, group=None):
        '''
        Remove group
        if group not specified, remove all groups
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        src_endpoint = 1
        if not group:
            data = struct.pack('!BHBBH', addr_mode, addr,
                               src_endpoint, endpoint)
            return self.send_data(0x0064, data)
        group = self.__addr(group)
        data = struct.pack('!BHBBH', addr_mode, addr,
                           src_endpoint, endpoint, group)
        r = self.send_data(0x0063, data)
        if r == 0:
            if group:
                del self._groups[self.__haddr(group)]
            else:
                self._groups = {}
        return r

    def identify_device(self, addr, time_sec=10):
        '''
        convenient function that automatically find destination endpoint
        '''
        device = self._devices[addr]
        device.identify_device(time_sec)

    def identify_send(self, addr, endpoint, time_sec):
        '''
        identify query
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBBH', 2, addr, 1, endpoint, time_sec)
        return self.send_data(0x0070, data)

    def identify_query(self, addr, endpoint):
        '''
        identify query
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBB', 2, addr, 1, endpoint)
        return self.send_data(0x0071, data)

    def initiate_touchlink(self):
        '''
        Initiate Touchlink
        '''
        return self.send_data(0x00D0)

    def touchlink_factory_reset(self):
        '''
        Touchlink factory reset
        '''
        return self.send_data(0x00D2)

    def read_attribute_request(self, addr, endpoint, cluster, attribute):
        '''
        Read Attribute request
        attribute can be a unique int or a list of int
        '''
        addr = self.__addr(addr)
        direction = 0
        manufacturer_specific = 0
        manufacturer_id = 0
        if not isinstance(attribute, list):
            attribute = [attribute]
        length = len(attribute)
        data = struct.pack('!BHBBHBBHB{}H'.format(length), 2, addr, 1, endpoint, cluster, 
                           direction, manufacturer_specific, 
                           manufacturer_id, length, *attribute)
        self.send_data(0x0100, data)

    def write_attribute_request(self, addr, endpoint, cluster, attribute):
        '''
        Write Attribute request
        attribute can be a unique int or a list of int
        '''
        addr = self.__addr(addr)
        direction = 0
        manufacturer_specific = 0
        manufacturer_id = 0
        if not isinstance(attribute, list):
            attribute = [attribute]
        length = len(attribute)
        data = struct.pack('!BHBBHBBHB{}H'.format(length), 2, addr, 1,
                           endpoint, cluster,
                           direction, manufacturer_specific,
                           manufacturer_id, length, *attribute)
        self.send_data(0x0110, data)

    def reporting_request(self, addr, endpoint, cluster, attribute, attribute_type):
        '''
        Configure reporting request
        for now support only one attribute
        '''
        addr = self.__addr(addr)
        direction = 0
        manufacturer_specific = 0
        manufacturer_id = 0
#         if not isinstance(attributes, list):
#             attributes = [attributes]
#         length = len(attributes)
        length = 1
        attribute_direction = 0
#         attribute_type = 0
        attribute_id = attribute
        min_interval = 0
        max_interval = 0
        timeout = 0
        change = 0
        data = struct.pack('!BHBBHBBHBBBHHHHB', 2, addr, 1, endpoint, cluster, 
                           direction, manufacturer_specific, 
                           manufacturer_id, length, attribute_direction,
                           attribute_type, attribute_id, min_interval,
                           max_interval, timeout, change)
        self.send_data(0x0120, data, 0x8120)

    def attribute_discovery_request(self, addr, endpoint, cluster):
        '''
        Attribute discovery request
        '''
        addr = self.__addr(addr)
        direction = 0
        manufacturer_specific = 0
        manufacturer_id = 0
        data = struct.pack('!BHBBHBBBHB', 2, addr, 1, endpoint, cluster, 
                           0, direction, manufacturer_specific,
                           manufacturer_id, 255)
        self.send_data(0x0140, data)

    def available_actions(self, addr, endpoint=None):
        '''
        Analyse specified endpoint to found available actions
        actions are:
        - onoff
        - move
        - lock
        - ...
        '''
        device = self.get_device_from_addr(addr)
        if device:
            return device.available_actions(endpoint)

    @register_actions(ACTIONS_ONOFF)
    def action_onoff(self, addr, endpoint, onoff, on_time=0, off_time=0, effect=0, gradient=0):
        '''
        On/Off action
        onoff :   0 - OFF
                1 - ON
                2 - Toggle
        on_time : timed on in sec
        off_time : timed off in sec
        effect : effect id
        gradient : effect gradient
        Note that timed onoff and effect are mutually exclusive
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBBB', 2, addr, 1, endpoint, onoff)
        cmd = 0x0092
        if on_time or off_time:
            cmd = 0x0093
            data += struct.pack('!HH', on_time, off_time)
        elif effect:
            cmd = 0x0094
            data = struct.pack('!BHBBBB', 2, addr, 1, endpoint, effect, gradient)
        self.send_data(cmd, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_level(self, addr, endpoint, onoff=OFF, mode=0, rate=0):
        '''
        move to level
        mode 0 up, 1 down
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBBBBB', 2, addr, 1, endpoint, onoff, mode, rate)
        self.send_data(0x0080, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_level_onoff(self, addr, endpoint, onoff=OFF, level=0, transition_time=0):
        '''
        move to level with on off
        level between 0 - 100
        '''
        addr = self.__addr(addr)
        level = int(level*254//100)
        data = struct.pack('!BHBBBBH', 2, addr, 1, endpoint, onoff, level, transition_time)
        self.send_data(0x0081, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_step(self, addr, endpoint, onoff=OFF, step_mode=0, step_size=0, transition_time=0):
        '''
        move step
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBBBBBH', 2, addr, 1, endpoint, onoff, step_mode, step_size, transition_time)
        self.send_data(0x0082, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_stop(self, addr, endpoint):
        '''
        move stop
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBB', 2, addr, 1, endpoint)
        self.send_data(0x0083, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_stop_onoff(self, addr, endpoint):
        '''
        move stop on off
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBB', 2, addr, 1, endpoint)
        self.send_data(0x0084, data)

    @register_actions(ACTIONS_HUE)
    def actions_move_hue(self, addr, endpoint, hue, direction=0, transition=0):
        '''
        move to hue
        hue 0-360 in degrees
        direction : 0 shortest, 1 longest, 2 up, 3 down
        transition in second
        '''
        addr = self.__addr(addr)
        hue = int(hue*254//360)
        data = struct.pack('!BHBBBBH', 2, addr, 1, endpoint,
                           hue, direction, transition)
        self.send_data(0x00B0, data)

    @register_actions(ACTIONS_HUE)
    def actions_move_hue_saturation(self, addr, endpoint, hue, saturation=100, transition=0):
        '''
        move to hue and saturation
        hue 0-360 in degrees
        saturation 0-100 in percent
        transition in second
        '''
        addr = self.__addr(addr)
        hue = int(hue*254//360)
        saturation = int(saturation*254//100)
        data = struct.pack('!BHBBBBH', 2, addr, 1, endpoint,
                           hue, saturation, transition)
        self.send_data(0x00B6, data)

    @register_actions(ACTIONS_HUE)
    def actions_move_hue_hex(self, addr, endpoint, color_hex, transition=0):
        '''
        move to hue color in #ffffff
        transition in second
        '''
        rgb = hex_to_rgb(color_hex)
        self.actions_move_hue_rgb(addr, endpoint, rgb, transition)

    @register_actions(ACTIONS_HUE)
    def actions_move_hue_rgb(self, addr, endpoint, rgb, transition=0):
        '''
        move to hue (r,g,b) example : (1.0, 1.0, 1.0)
        transition in second
        '''
        hue, saturation, level = colorsys.rgb_to_hsv(*rgb)
        hue = int(hue*360)
        saturation = int(saturation*100)
        level = int(level*100)
        self.action_move_level_onoff(addr, endpoint, ON, level, 0)
        self.actions_move_hue_saturation(addr, endpoint, hue, saturation, transition)

    @register_actions(ACTIONS_COLOR)
    def actions_move_colour(self, addr, endpoint, x, y, transition=0):
        '''
        move to colour x y
        x, y can be integer 0-65536 or float 0-1.0
        transition in second
        '''
        if isinstance(x, float) and x <= 1:
            x = int(x*65536)
        if isinstance(y, float) and y <= 1:
            y = int(y*65536)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBHHH', 2, addr, 1, endpoint,
                           x, y, transition)
        self.send_data(0x00B7, data)

    @register_actions(ACTIONS_COLOR)
    def actions_move_colour_hex(self, addr, endpoint, color_hex, transition=0):
        '''
        move to colour #ffffff
        convenient function to set color in hex format
        transition in second
        '''
        x, y = hex_to_xy(color_hex)
        return self.actions_move_colour(addr, endpoint, x, y, transition)

    @register_actions(ACTIONS_COLOR)
    def actions_move_colour_rgb(self, addr, endpoint, rgb, transition=0):
        '''
        move to colour (r,g,b) example : (1.0, 1.0, 1.0)
        convenient function to set color in hex format
        transition in second
        '''
        x, y = rgb_to_xy(rgb)
        return self.actions_move_colour(addr, endpoint, x, y, transition)

    @register_actions(ACTIONS_TEMPERATURE)
    def actions_move_temperature(self, addr, endpoint, temperature, transition=0):
        '''
        move colour to temperature
        temperature unit is kelvin
        transition in second
        '''
        temperature = int(1000000//temperature)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBHH', 2, addr, 1, endpoint,
                           temperature, transition)
        self.send_data(0x00C0, data)

    @register_actions(ACTIONS_LOCK)
    def action_lock(self, addr, endpoint, lock):
        '''
        Lock / unlock
        '''
        addr = self.__addr(addr)
        data = struct.pack('!BHBBB', 2, addr, 1, endpoint, lock)
        self.send_data(0x00f0, data)

    def start_mqtt_broker(self, host='localhost:1883', username=None, password=None):
        '''
        Start a MQTT broker in a new thread 
        '''
        from .mqtt_broker import MQTT_Broker
        broker = MQTT_Broker(self, host, username, password)
        broker.connect()
        self.broker_thread = threading.Thread(target=broker.client.loop_forever)
        self.broker_thread.start()


class ZiGateWiFi(ZiGate):
    def __init__(self, host, port=None, path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True):
        self._host = host
        ZiGate.__init__(self, port=port, path=path,
                        auto_start=auto_start,
                        auto_save=auto_save
                        )

    def setup_connection(self):
        self.connection = ThreadSocketConnection(self, self._host, self._port)

    def reboot(self):
        '''
        ask zigate wifi to reboot
        '''
        import requests
        r = requests.get('http://{}/reboot'.format(self._host))


class DeviceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Device):
            return obj.to_json()
        if isinstance(obj, Cluster):
            return obj.to_json()
        elif isinstance(obj, bytes):
            return hexlify(obj).decode()
        return json.JSONEncoder.default(self, obj)


class Device(object):
    def __init__(self, info=None, zigate_instance=None):
        self._zigate = zigate_instance
        self._lock = threading.Lock()
        self.info = info or {}
        self.endpoints = {}
        self._expire_timer = {}
        self.missing = False

    def available_actions(self, endpoint_id=None):
        '''
        Analyse specified endpoint to found available actions
        actions are:
        - onoff
        - move
        - lock
        - ...
        '''
        actions = {}
        if not endpoint_id:
            endpoint_id = list(self.endpoints.keys())
        if not isinstance(endpoint_id, list):
            endpoint_id = [endpoint_id]
        for ep_id in endpoint_id:
            actions[ep_id] = []
            endpoint = self.endpoints.get(ep_id)
            if endpoint:
                if endpoint['device'] in ACTUATORS:
                    if 0x0006 in endpoint['in_clusters']:
                        # Oh please XIAOMI, respect the standard...
                        if ep_id != 1 and self.get_property_value('type') == 'lumi.ctrl_neutral1':
                            ep_id -= 1
                        actions[ep_id].append(ACTIONS_ONOFF)
                    if 0x0008 in endpoint['in_clusters']:
                        actions[ep_id].append(ACTIONS_LEVEL)
                    if 0x0101 in endpoint['in_clusters']:
                        actions[ep_id].append(ACTIONS_LOCK)
                    if 0x0300 in endpoint['in_clusters']:
                        if endpoint['device'] == 0x0210:
                            actions[ep_id].append(ACTIONS_HUE)
                        elif endpoint['device'] == 0x0220:
                            actions[ep_id].append(ACTIONS_TEMPERATURE)
                        else: # 0x0200
                            actions[ep_id].append(ACTIONS_COLOR)
        return actions

    def _create_actions(self):
        '''
        create convenient functions for actions
        '''
        a_actions = self.available_actions()
        for endpoint_id, actions in a_actions.items():
            for action in actions:
                for func_name in ACTIONS.get(action, []):
                    func = getattr(self._zigate, func_name)
                    wfunc = functools.partial(func, self.addr, endpoint_id)
                    functools.update_wrapper(wfunc, func)
                    setattr(self, func_name, wfunc)

    def _bind_report(self, enpoint_id=None):
        '''
        automatically bind and report data for light
        '''
        if not BIND_REPORT_LIGHT:
            return
        if enpoint_id:
            endpoints_list = [(enpoint_id, self.endpoints[enpoint_id])]
        else:
            endpoints_list = self.endpoints.items()
        for endpoint_id, endpoint in endpoints_list:
            if endpoint['device'] in ACTUATORS:  # light
                if 0x0006 in endpoint['in_clusters']:
                    LOGGER.debug('bind and report for cluster 0x0006')
                    self._zigate.bind(self.ieee, endpoint_id, 0x0006)
                    self._zigate.reporting_request(self.addr, endpoint_id,
                                                   0x0006, 0x0000, 0x10)  # TODO: auto select data type
                if 0x0008 in endpoint['in_clusters']:
                    LOGGER.debug('bind and report for cluster 0x0008')
                    self._zigate.bind(self.ieee, endpoint_id, 0x0008)
                    self._zigate.reporting_request(self.addr, endpoint_id,
                                                   0x0008, 0x0000, 0x20)
                # TODO : auto select data type
                # TODO : check if the following is needed
                if 0x0300 in endpoint['in_clusters']:
                    LOGGER.debug('bind and report for cluster 0x0300')
                    self._zigate.bind(self.ieee, endpoint_id, 0x0300)
                    for i in range(9):  # all color informations
                        self._zigate.reporting_request(self.addr, endpoint_id,
                                                       0x0300, i, 0x20)

    @staticmethod
    def from_json(data, zigate_instance=None):
        d = Device(zigate_instance=zigate_instance)
        d.info = data.get('info', {})
        for ep in data.get('endpoints', []):
            if 'attributes' in ep:  # old version
                LOGGER.debug('Old version found, convert it')
                for attribute in ep['attributes'].values():
                    endpoint_id = attribute['endpoint']
                    cluster_id = attribute['cluster']
                    data = {'attribute': attribute['attribute'],
                            'data': attribute['data'],
                            }
                    d.set_attribute(endpoint_id, cluster_id, data)
            else:
                endpoint = d.get_endpoint(ep['endpoint'])
                endpoint['profile'] = ep.get('profile', 0)
                endpoint['device'] = ep.get('device', 0)
                endpoint['in_clusters'] = ep.get('in_clusters', [])
                endpoint['out_clusters'] = ep.get('out_clusters', [])
                for cl in ep['clusters']:
                    cluster = Cluster.from_json(cl)
                    endpoint['clusters'][cluster.cluster_id] = cluster
        if 'power_source' in d.info:  # old version
            d.info['power_type'] = d.info.pop('power_source')
        d._avoid_duplicate()
        return d

    def to_json(self, properties=False):
        r = {'addr': self.addr,
             'info': self.info,
             'endpoints': [{'endpoint': k,
                            'clusters': list(v['clusters'].values()),
                            'profile': v['profile'],
                            'device': v['device'],
                            'in_clusters': v['in_clusters'],
                            'out_clusters': v['out_clusters']
                            } for k, v in self.endpoints.items()],
             }
        if properties:
            r['properties'] = list(self.properties)
        return r

    def __str__(self):
        name = ''
        typ = self.get_property('type')
        if typ:
            name = typ['value']
        return 'Device {} {}'.format(self.addr, name)

    def __repr__(self):
        return self.__str__()

    @property
    def addr(self):
        return self.info['addr']

    @property
    def ieee(self):
        return self.info.get('ieee')

    @property
    def rssi(self):
        return self.info.get('rssi', 0)

    @rssi.setter
    def rssi(self, value):
        self.info['rssi'] = value

    @property
    def battery_percent(self):
        percent = self.get_property_value('battery_percent')
        if not percent:
            percent = 100
            if self.info.get('power_type') == 0:
                power_source = self.get_property_value('power_source')
                if power_source is None:
                    power_source = 3
                battery = self.get_property_value('battery')
                if power_source == 3:  # battery
                    power_source = 3.2
                if power_source and battery:
                    power_end = 0.9*power_source
                    percent = (battery-power_end)*100/(power_source-power_end)
                if percent > 100:
                    percent = 100
        return percent

    @property
    def rssi_percent(self):
        return round(100*self.rssi/255)

    def refresh_device(self):
        self._zigate.refresh_device(self.addr)

    def identify_device(self, time_sec=10):
        '''
        send identify command
        sec is time in second
        '''
        ep = list(self.endpoints.keys())
        ep.sort()
        if ep:
            endpoint = ep[0]
        else:
            endpoint = 1
        self._zigate.identify_send(self.addr, endpoint, time_sec)

    def __setitem__(self, key, value):
        self.info[key] = value

    def __getitem__(self, key):
        return self.info[key]

    def __delitem__(self, key):
        return self.info.__delitem__(key)

    def get(self, key, default):
        return self.info.get(key, default)

    def __contains__(self, key):
        return self.info.__contains__(key)

    def __len__(self):
        return len(self.info)

    def __iter__(self):
        return self.info.__iter__()

    def items(self):
        return self.info.items()

    def keys(self):
        return self.info.keys()

#     def __getattr__(self, attr):
#         return self.info[attr]

    def update(self, device):
        '''
        update from other device
        '''
        self._lock.acquire()
        self.info.update(device.info)
        self.endpoints.update(device.endpoints)
#         self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self._lock.release()

    def update_info(self, info):
        self._lock.acquire()
        self.info.update(info)
        self._lock.release()

    def get_endpoint(self, endpoint_id):
        self._lock.acquire()
        if endpoint_id not in self.endpoints:
            self.endpoints[endpoint_id] = {'clusters': {},
                                           'profile': 0,
                                           'device': 0,
                                           'in_clusters': [],
                                           'out_clusters': [],
                                           }
        self._lock.release()
        return self.endpoints[endpoint_id]

    def get_cluster(self, endpoint_id, cluster_id):
        endpoint = self.get_endpoint(endpoint_id)
        self._lock.acquire()
        if cluster_id not in endpoint['clusters']:
            cluster = get_cluster(cluster_id)
            endpoint['clusters'][cluster_id] = cluster
        self._lock.release()
        return endpoint['clusters'][cluster_id]

    def set_attribute(self, endpoint_id, cluster_id, data):
        added = False
        rssi = data.pop('rssi', 0)
        if rssi > 0:
            self.info['rssi'] = rssi
        self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self.missing = False
        cluster = self.get_cluster(endpoint_id, cluster_id)
        self._lock.acquire()
        r = cluster.update(data)
        if r:
            added, attribute = r
            if 'expire' in attribute:
                self._set_expire_timer(endpoint_id, cluster_id,
                                       attribute['attribute'],
                                       attribute['expire'])
        self._avoid_duplicate()
        self._lock.release()
        if not r:
            return
        return added, attribute['attribute']

    def _set_expire_timer(self, endpoint_id, cluster_id, attribute_id, expire):
        LOGGER.debug('Set expire timer for {}-{}-{} in {}'.format(endpoint_id,
                                                                  cluster_id,
                                                                  attribute_id,
                                                                  expire))
        k = (endpoint_id, cluster_id, attribute_id)
        timer = self._expire_timer.get(k)
        if timer:
            timer.cancel()
        timer = threading.Timer(expire,
                                functools.partial(self._reset_attribute,
                                                  endpoint_id,
                                                  cluster_id,
                                                  attribute_id))
        timer.setDaemon(True)
        timer.start()

    def _reset_attribute(self, endpoint_id, cluster_id, attribute_id):
        attribute = self.get_attribute(endpoint_id,
                                       cluster_id,
                                       attribute_id)
        value = attribute['value']
        if 'expire_value' in attribute:
            new_value = attribute['expire_value']
        else:
            new_value = type(value)()
        attribute['value'] = new_value
        attribute['data'] = new_value
        attribute = self.get_attribute(endpoint_id,
                                       cluster_id,
                                       attribute_id,
                                       True)
        dispatch_signal(ZIGATE_ATTRIBUTE_UPDATED, self._zigate,
                        **{'zigate': self._zigate,
                           'device': self,
                           'attribute': attribute})

    def get_attribute(self, endpoint_id, cluster_id, attribute_id,
                      extended_info=False):
        if endpoint_id in self.endpoints:
            endpoint = self.endpoints[endpoint_id]
            if cluster_id in endpoint['clusters']:
                cluster = endpoint['clusters'][cluster_id]
                attribute = cluster.get_attribute(attribute_id)
                if extended_info:
                    attr = {'endpoint': endpoint_id,
                            'cluster': cluster_id,
                            'addr': self.addr}
                    attr.update(attribute)
                    return attr
                return attribute

    @property
    def attributes(self):
        '''
        list all attributes including endpoint and cluster id
        '''
        return self.get_attributes(True)

    def get_attributes(self, extended_info=False):
        '''
        list all attributes
        including endpoint and cluster id
        '''
        attrs = []
        endpoints = list(self.endpoints.keys())
        endpoints.sort()
        for endpoint_id in endpoints:
            endpoint = self.endpoints[endpoint_id]
            for cluster_id, cluster in endpoint.get('clusters', {}).items():
                for attribute in cluster.attributes.values():
                    if extended_info:
                        attr = {'endpoint': endpoint_id, 'cluster': cluster_id}
                        attr.update(attribute)
                        attrs.append(attr)
                    else:
                        attrs.append(attribute)
        return attrs

    def set_attributes(self, attributes):
        '''
        load list created by attributes()
        '''
        for attribute in attributes:
            endpoint_id = attribute.pop('endpoint')
            cluster_id = attribute.pop('cluster')
            self.set_attribute(endpoint_id, cluster_id, attribute)

    def get_property(self, name, extended_info=False):
        '''
        return attribute matching name
        '''
        for endpoint_id, endpoint in self.endpoints.items():
            for cluster_id, cluster in endpoint.get('clusters', {}).items():
                for attribute in cluster.attributes.values():
                    if attribute.get('name') == name:
                        if extended_info:
                            attr = {'endpoint': endpoint_id,
                                    'cluster': cluster_id}
                            attr.update(attribute)
                            return attr
                        return attribute

    def get_property_value(self, name, default=None):
        '''
        return attribute value matching name
        '''
        prop = self.get_property(name)
        if prop:
            return prop.get('value', default)
        return default

    def get_value(self, name, default=None):
        '''
        return attribute value matching name
        shorter alias of get_property_value
        '''
        return self.get_property_value(name, default)

    @property
    def properties(self):
        '''
        return well known attribute list
        attribute with friendly name
        '''
        props = []
        for endpoint in self.endpoints.values():
            for cluster in endpoint.get('clusters', {}).values():
                for attribute in cluster.attributes.values():
                    if 'name' in attribute:
                        props.append(attribute)
        return props

    def receiver_on_when_idle(self):
        mac_capability = self.info.get('mac_capability')
        if mac_capability:
            return mac_capability[-3] == '1'
        return False

    def need_refresh(self):
        '''
        return True if device need to be refresh
        because of missing important information
        '''
        need = False
        LOGGER.debug('Check Need refresh {}'.format(self))
        if not self.get_property_value('type'):
            LOGGER.debug('Need refresh : no type')
            need = True
        if not self.ieee:
            LOGGER.debug('Need refresh : no IEEE')
            need = True
        if not self.endpoints:
            LOGGER.debug('Need refresh : no endpoints')
            need = True
        for endpoint in self.endpoints.values():
            if endpoint.get('device') is None:
                LOGGER.debug('Need refresh : no device id')
                need = True
            if endpoint.get('in_clusters') is None:
                LOGGER.debug('Need refresh : no clusters list')
                need = True
        return need

    def _avoid_duplicate(self):
        '''
        Rename attribute if needed to avoid duplicate
        '''
        properties = []
        for attribute in self.attributes:
            if 'name' not in attribute:
                continue
            if attribute['name'] in properties:
                attribute['name'] = '{}{}'.format(attribute['name'],
                                                  attribute['endpoint'])
                attr = self.get_attribute(attribute['endpoint'],
                                          attribute['cluster'],
                                          attribute['attribute'])
                attr['name'] = attribute['name']
            properties.append(attribute['name'])

