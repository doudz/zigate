#! /usr/bin/python3
#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

from binascii import hexlify
import traceback
from time import (sleep, strftime, time)
import logging
import json
import os
from shutil import copyfile
from pydispatch import dispatcher
from .transport import (ThreadSerialConnection,
                        ThreadSocketConnection,
                        FakeTransport)
from .responses import (RESPONSES, Response)
from .const import (ACTIONS_COLOR, ACTIONS_LEVEL, ACTIONS_LOCK, ACTIONS_HUE,
                    ACTIONS_ONOFF, ACTIONS_TEMPERATURE, ACTIONS_COVER,
                    OFF, ON, TYPE_COORDINATOR, STATUS_CODES,
                    ZIGATE_ATTRIBUTE_ADDED, ZIGATE_ATTRIBUTE_UPDATED,
                    ZIGATE_DEVICE_ADDED, ZIGATE_DEVICE_REMOVED,
                    ZIGATE_DEVICE_UPDATED, ZIGATE_DEVICE_ADDRESS_CHANGED,
                    ZIGATE_PACKET_RECEIVED, ZIGATE_DEVICE_NEED_DISCOVERY,
                    ZIGATE_RESPONSE_RECEIVED, DATA_TYPE, BASE_PATH)

from .clusters import (Cluster, get_cluster)
import functools
import struct
import threading
import random
from enum import Enum
import colorsys
import datetime
try:
    import RPi.GPIO as GPIO
except Exception:
    pass


LOGGER = logging.getLogger('zigate')


AUTO_SAVE = 5 * 60  # 5 minutes
BIND_REPORT = True  # automatically bind and report state for light
SLEEP_INTERVAL = 0.1
ACTIONS = {}
WAIT_TIMEOUT = 3

# Device id
ACTUATORS = [0x0010, 0x0051,
             0x010a, 0x010b,
             0x0100, 0x0101, 0x0102, 0x0103, 0x0105, 0x0110,
             0x0200, 0x0202, 0x0210, 0x0220]
#             On/off light 0x0000
#             On/off plug-in unit 0x0010
#             Dimmable light 0x0100
#             Dimmable plug-in unit 0x0110
#             Color light 0x0200
#             Extended color light 0x0210
#             Color temperature light 0x0220
# On/Off Light 0x0100 Section 3.1
# Dimmable Light 0x0101 Section 3.2
# Colour Dimmable Light 0x0102 Section 3.3
# On/Off Light Switch 0x0103 Section 3.4
# Dimmer Switch 0x0104 Section 3.5
# Colour Dimmer Switch 0x0105 Section 3.6
# Light Sensor 0x0106 Section 3.7
# Occupancy Sensor 0x0107 Section 3.8
# On/Off Ballast 0x0108 Section 3.9
# Dimmable Ballast 0x0109 Section 3.10
# On/Off Plug-in Unit 0x010A Section 3.11
# Dimmable Plug-in Unit 0x010B Section 3.12
# Colour Temperature Light 0x010C Section 3.13
# Extended Colour Light 0x010D Section 3.14
# Light Level Sensor 0x010E Section 3.15
# Colour Controller 0x0800 Section 3.16
# Colour Scene Controller 0x0810 Section 3.17
# Non-Colour Controller 0x0820 Section 3.18
# Non-Colour Scene Controller 0x0830 Section 3.19
# Control Bridge 0x0840 Section 3.20
# On/Off Sensor 0x0850 Section 3.21


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
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


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
                 auto_save=True,
                 channel=None,
                 adminpanel=False):
        self._devices = {}
        self._groups = {}
        self._scenes = {}
        self._path = path
        self._version = None
        self._port = port
        self._last_response = {}  # response to last command type
        self._last_status = {}  # status to last command type
        self._save_lock = threading.Lock()
        self._autosavetimer = None
        self._closing = False
        self.connection = None

        self._addr = '0000'
        self._ieee = None
        self.panid = 0
        self.extended_panid = 0
        self.channel = 0
        self._started = False
        self._no_response_count = 0

#         self._event_thread = threading.Thread(target=self._event_loop,
#                                               name='ZiGate-Event Loop')
#         self._event_thread.setDaemon(True)
#         self._event_thread.start()

        self._ota_reset_local_variables()

        if adminpanel:
            self.start_adminpanel()

        if auto_start:
            self.startup(channel)
            if auto_save:
                self.start_auto_save()

    @property
    def ieee(self):
        return self._ieee

    @property
    def addr(self):
        return self._addr

    def start_adminpanel(self):
        '''
        Start Admin panel in other thread
        '''
        from .adminpanel import start_adminpanel
        start_adminpanel(self)

    def _event_loop(self):
        while not self._closing:
            if self.connection and not self.connection.received.empty():
                packet = self.connection.received.get()
                dispatch_signal(ZIGATE_PACKET_RECEIVED, self, packet=packet)
                t = threading.Thread(target=self.decode_data, args=(packet,),
                                     name='ZiGate-Decode data')
                t.setDaemon(True)
                t.start()
#                 self.decode_data(packet)
            else:
                sleep(SLEEP_INTERVAL)

    def setup_connection(self):
        self.connection = ThreadSerialConnection(self, self._port)

    def close(self):
        self._closing = True
        if self._autosavetimer:
            self._autosavetimer.cancel()
        try:
            if self.connection:
                self.connection.close()
        except Exception:
            LOGGER.error('Exception during closing')
            LOGGER.error(traceback.format_exc())
        self.connection = None
        self._started = False

    def save_state(self, path=None):
        LOGGER.debug('Saving persistent file')
        path = path or self._path
        if path is None:
            LOGGER.warning('Persistent file is disabled')
            if self._autosavetimer:
                self._autosavetimer.cancel()
            return
        self._path = os.path.expanduser(path)
        backup_path = self._path + '.0'
        r = self._save_lock.acquire(True, 5)
        if not r:
            LOGGER.error('Failed to acquire Lock to save persistent file')
            return
        try:
            if os.path.exists(self._path):
                LOGGER.debug('File already existing, make a backup before')
                copyfile(self._path, backup_path)
        except Exception:
            LOGGER.error('Failed to create backup, cancel saving.')
            LOGGER.error(traceback.format_exc())
            self._save_lock.release()
            return
        try:
            data = {'devices': list(self._devices.values()),
                    'groups': self._groups,
                    'scenes': self._scenes
                    }
            with open(self._path, 'w') as fp:
                json.dump(data, fp, cls=DeviceEncoder,
                          sort_keys=True, indent=4, separators=(',', ': '))
        except Exception:
            LOGGER.error('Failed to save persistent file {}'.format(self._path))
            LOGGER.error(traceback.format_exc())
            LOGGER.error('Restoring backup...')
            copyfile(backup_path, self._path)
        self._save_lock.release()

    def load_state(self, path=None):
        LOGGER.debug('Try loading persistent file')
        path = path or self._path
        if path is None:
            LOGGER.warning('Persistent file is disabled')
            return
        self._path = os.path.expanduser(path)
        backup_path = self._path + '.0'
        if os.path.exists(self._path):
            try:
                with open(self._path) as fp:
                    data = json.load(fp)
                if not isinstance(data, dict):  # old version
                    data = {'devices': data, 'groups': {}}
                groups = data.get('groups', {})
                for k, v in groups.items():
                    groups[k] = set([tuple(r) for r in v])
                self._groups = groups
                self._scenes = data.get('scenes', {})
                devices = data.get('devices', [])
                for data in devices:
                    try:
                        device = Device.from_json(data, self)
                        self._devices[device.addr] = device
                        device._create_actions()
                    except Exception:
                        LOGGER.error('Error loading device {}'.format(data))
                LOGGER.debug('Load success')
                return True
            except Exception:
                LOGGER.error('Failed to load persistent file {}'.format(self._path))
                LOGGER.error(traceback.format_exc())
                if os.path.exists(backup_path):
                    LOGGER.warning('A backup exists {}, you should consider restoring it.'.format(backup_path))
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

    def _start_event_thread(self):
        self._event_thread = threading.Thread(target=self._event_loop,
                                              name='ZiGate-Event Loop')
        self._event_thread.setDaemon(True)
        self._event_thread.start()

    def autoStart(self, channel=None):
        self.startup(channel)

    def startup(self, channel=None):
        '''
        Startup sequence:
            - Load persistent file
            - setup connection
            - Set Channel mask
            - Set Type Coordinator
            - Start Network
            - Refresh devices list
        '''
        if self._started:
            return
        self._closing = False
        self._start_event_thread()
        self.load_state()
        self.setup_connection()
        version = self.get_version()
        self.set_channel(channel)
        self.set_type(TYPE_COORDINATOR)
        LOGGER.debug('Check network state')
        # self.start_network()
        network_state = self.get_network_state()
        if not network_state:
            LOGGER.error('Failed to get network state')
        if not network_state or network_state.get('extended_panid') == 0 or \
           network_state.get('addr') == 'ffff':
            LOGGER.debug('Network is down, start it')
            self.start_network(True)

        if version and version['version'] >= '3.0f':
            LOGGER.debug('Set Zigate Time (firmware >= 3.0f)')
            self.set_time()
        self.get_devices_list(True)
        t = threading.Thread(target=self.need_discovery)
        t.setDaemon(True)
        t.start()
#         self.need_discovery()

    def need_discovery(self):
        '''
        scan device which need discovery
        auto discovery if possible
        else dispatch signal
        '''
        for device in self.devices:
            if device.need_discovery():
                if device.receiver_on_when_idle():
                    LOGGER.debug('Auto discover device {}'.format(device))
                    device.discover_device()
                else:
                    dispatch_signal(ZIGATE_DEVICE_NEED_DISCOVERY,
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

    def send_data(self, cmd, data="", wait_response=None, wait_status=True):
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
        LOGGER.debug('Encoded Msg to send {}'.format(hexlify(encoded_output)))

        self.send_to_transport(encoded_output)
        if wait_status:
            status = self._wait_status(cmd)
            if wait_response and status is not None:
                r = self._wait_response(wait_response)
                return r
            return status
        return False

    def decode_data(self, packet):
        '''
        Decode raw packet message
        '''
        try:
            decoded = self.zigate_decode(packet[1:-1])
            msg_type, length, checksum, value, lqi = \
                struct.unpack('!HHB%dsB' % (len(decoded) - 6), decoded)
        except Exception:
            LOGGER.error('Failed to decode packet : {}'.format(hexlify(packet)))
            return
        if length != len(value) + 1:  # add lqi length
            LOGGER.error('Bad length {} != {} : {}'.format(length,
                                                           len(value) + 1,
                                                           value))
            return
        computed_checksum = self.checksum(decoded[:4], lqi, value)
        if checksum != computed_checksum:
            LOGGER.error('Bad checksum {} != {}'.format(checksum,
                                                        computed_checksum))
            return
        LOGGER.debug('Received response 0x{:04x}: {}'.format(msg_type, hexlify(value)))
        try:
            response = RESPONSES.get(msg_type, Response)(value, lqi)
        except Exception:
            LOGGER.error('Error decoding response 0x{:04x}: {}'.format(msg_type, hexlify(value)))
            LOGGER.error(traceback.format_exc())
            return
        if msg_type != response.msg:
            LOGGER.warning('Unknown response 0x{:04x}'.format(msg_type))
        LOGGER.debug(response)
        self._last_response[msg_type] = response
        self.interpret_response(response)
        dispatch_signal(ZIGATE_RESPONSE_RECEIVED, self, response=response)

    def interpret_response(self, response):
        if response.msg == 0x8000:  # status
            if response['status'] != 0:
                LOGGER.error('Command 0x{:04x} failed {} : {}'.format(response['packet_type'],
                                                                      response.status_text(),
                                                                      response['error']))
            self._last_status[response['packet_type']] = response
        elif response.msg == 0x8007:  # factory reset
            if response['status'] == 0:
                self._devices = {}
                self.start_network()
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
                if d['ieee'] == '0000000000000000':
                    continue
                device = Device(dict(d), self)
                self._set_device(device)
        elif response.msg == 0x8042:  # node descriptor
            addr = response['addr']
            d = self.get_device_from_addr(addr)
            if d:
                d.update_info(response.cleaned_data())
                self.discover_device(addr)
        elif response.msg == 0x8043:  # simple descriptor
            addr = response['addr']
            endpoint = response['endpoint']
            d = self.get_device_from_addr(addr)
            if d:
                ep = d.get_endpoint(endpoint)
                ep.update(response.cleaned_data())
                ep['in_clusters'] = response['in_clusters']
                ep['out_clusters'] = response['out_clusters']
                self.discover_device(addr)
                d._create_actions()
        elif response.msg == 0x8045:  # endpoint list
            addr = response['addr']
            d = self.get_device_from_addr(addr)
            if d:
                for endpoint in response['endpoints']:
                    ep = d.get_endpoint(endpoint['endpoint'])
                    self.simple_descriptor_request(addr, endpoint['endpoint'])
                self.discover_device(addr)
        elif response.msg == 0x8048:  # leave
            device = self.get_device_from_ieee(response['ieee'])
            if device:
                if response['rejoin_status'] == 1:
                    device.missing = True
                else:
                    self._remove_device(device.addr)
        elif response.msg == 0x8062:  # Get group membership response
            data = response.cleaned_data()
            self._sync_group_membership(data['addr'], data['endpoint'], data['groups'])
        elif response.msg in (0x8100, 0x8102, 0x8110, 0x8401,
                              0x8085, 0x8095, 0x80A7):  # attribute report or IAS Zone status change
            if response.get('status', 0) != 0:
                LOGGER.debug('Received Bad status')
                # handle special case, no model identifier
                if response['status'] == 0x86 and response['cluster'] == 0 and response['attribute'] == 5:
                    response['data'] = 'unsupported'
                else:
                    return
            # ignore if related to zigate
            if response['addr'] == self.addr:
                return
            device = self._get_device(response['addr'])
            device.lqi = response['lqi']
            r = device.set_attribute(response['endpoint'],
                                     response['cluster'],
                                     response.cleaned_data())
            if r is None:
                return
            added, attribute_id = r
            changed = device.get_attribute(response['endpoint'],
                                           response['cluster'],
                                           attribute_id, True)
            if response['cluster'] == 0 and attribute_id == 5:
                if not device.discovery:
                    device.load_template()
            if added:
                dispatch_signal(ZIGATE_ATTRIBUTE_ADDED, self, **{'zigate': self,
                                                                 'device': device,
                                                                 'attribute': changed})
            else:
                dispatch_signal(ZIGATE_ATTRIBUTE_UPDATED, self, **{'zigate': self,
                                                                   'device': device,
                                                                   'attribute': changed})
        elif response.msg == 0x004D:  # device announce
            LOGGER.debug('Device Announce {}'.format(response))
            device = Device(response.data, self)
            self._set_device(device)
        elif response.msg == 0x8140:  # attribute discovery
            if 'addr' in response:
                # ignore if related to zigate
                if response['addr'] == self.addr:
                    return
                device = self._get_device(response['addr'])
                r = device.set_attribute(response['endpoint'],
                                         response['cluster'],
                                         response.cleaned_data())
        elif response.msg == 0x8501:  # OTA image block request
            LOGGER.debug('Client is requesting ota image data')
            self._ota_send_image_data(response)
        elif response.msg == 0x8503:  # OTA Upgrade end request
            LOGGER.debug('Client ended ota process')
            self._ota_handle_upgrade_end_request(response)
        elif response.msg == 0x8702:  # APS Data confirm Fail
            LOGGER.error(response)
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
        last_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        last_24h = last_24h.strftime('%Y-%m-%d %H:%M:%S')
        if addr in self._devices:
            if self._devices[addr].last_seen and self._devices[addr].last_seen < last_24h:
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
        device = self._devices.pop(addr)
        dispatch_signal(ZIGATE_DEVICE_REMOVED, **{'zigate': self,
                                                  'addr': addr,
                                                  'device': device})

    def _set_device(self, device):
        '''
        add/update device to cache list
        '''
        assert type(device) == Device
        if device.addr in self._devices:
            self._devices[device.addr].update(device)
            dispatch_signal(ZIGATE_DEVICE_UPDATED, self, **{'zigate': self,
                                                            'device': self._devices[device.addr]})
        else:
            # check if device already exist with other address
            d = self.get_device_from_ieee(device.ieee)
            if d:
                LOGGER.warning('Device already exists with another addr {}, rename it.'.format(d.addr))
                old_addr = d.addr
                new_addr = device.addr
                d.discovery = ''
                d.update(device)
                self._devices[new_addr] = d
                del self._devices[old_addr]
                dispatch_signal(ZIGATE_DEVICE_ADDRESS_CHANGED, self,
                                **{'zigate': self,
                                   'device': d,
                                   'old_addr': old_addr,
                                   'new_addr': new_addr,
                                   })
            else:
                self._devices[device.addr] = device
                dispatch_signal(ZIGATE_DEVICE_ADDED, self, **{'zigate': self,
                                                              'device': device})
            self.discover_device(device.addr)

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
            if t2 - t1 > WAIT_TIMEOUT:  # no response timeout
                LOGGER.warning('No response waiting command 0x{:04x}'.format(msg_type))
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
            if t2 - t1 > WAIT_TIMEOUT:  # no response timeout
                self._no_response_count += 1
                LOGGER.warning('No response after command 0x{:04x} ({})'.format(cmd, self._no_response_count))
                return
        self._no_response_count = 0
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
            r = self.send_data(0x0010, wait_response=0x8010)
            if r:
                self._version = r.data
            else:
                LOGGER.warning('Failed to retrieve zigate firmware version')
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
        return self.send_data(0x0011, wait_status=False)

    def erase_persistent(self):
        '''
        erase persistent data in zigate
        '''
        return self.send_data(0x0012, wait_status=False)

    def factory_reset(self):
        '''
        ZLO/ZLL "Factory New" Reset
        '''
        return self.send_data(0x0013, wait_status=False)

    def is_permitting_join(self):
        '''
        check if zigate is permitting join
        '''
        r = self.send_data(0x0014, wait_response=0x8014)
        if r:
            r = r.get('status', False)
        return r

    def set_time(self, dt=None):
        '''
        Set internal zigate time
        dt should be datetime.datetime object
        '''
        dt = dt or datetime.datetime.now()
        # timestamp from 2000-01-01 00:00:00
        timestamp = int((dt - datetime.datetime(2000, 1, 1)).total_seconds())
        data = struct.pack('!L', timestamp)
        self.send_data(0x0016, data)

    def get_time(self):
        '''
        get internal zigate time
        '''
        r = self.send_data(0x0017, wait_response=0x8017)
        dt = None
        if r:
            timestamp = r.get('timestamp')
            dt = datetime.datetime(2000, 1, 1) + datetime.timedelta(seconds=timestamp)
        return dt

    def set_led(self, on=True):
        '''
        Set Blue Led state ON/OFF
        '''
        data = struct.pack('!?', on)
        return self.send_data(0x0018, data)

    def set_certification(self, standard=1):
        '''
        Set Certification CE=1, FCC=2
        '''
        data = struct.pack('!B', standard)
        return self.send_data(0x0019, data)

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

    def set_extended_panid(self, panid):
        '''
        Set Extended PANID
        '''
        data = struct.pack('!Q', panid)
        return self.send_data(0x0020, data)

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
            self.panid = data['panid']
            self.extended_panid = data['extended_panid']
            self.channel = data['channel']
            return data

    def start_network(self, wait=False):
        ''' start network '''
        wait_response = None
        if wait:
            wait_response = 0x8024
        r = self.send_data(0x0024, wait_response=wait_response)
        if wait and r:
            data = r.cleaned_data()
            self._addr = data['addr']
            self._ieee = data['ieee']
            self.channel = data['channel']
        return r

    def start_network_scan(self):
        ''' start network scan '''
        return self.send_data(0x0025)

    def remove_device(self, addr):
        ''' remove device '''
        if addr in self._devices:
            ieee = self._devices[addr]['ieee']
            ieee = self.__addr(ieee)
            zigate_ieee = self.__addr(self.ieee)
            data = struct.pack('!QQ', zigate_ieee, ieee)
            return self.send_data(0x0026, data)

    def remove_device_ieee(self, ieee):
        ''' remove device '''
        device = self.get_device_from_ieee(ieee)
        if device:
            self.remove_device(device.addr)

    def enable_permissions_controlled_joins(self, enable=True):
        '''
        Enable Permissions Controlled Joins
        '''
        enable = 1 if enable else 2
        data = struct.pack('!B', enable)
        return self.send_data(0x0027, data)

    def _choose_addr_mode(self, addr_ieee):
        '''
        Choose the right address mode
        '''
        if len(addr_ieee) == 4:
            if addr_ieee in self._groups:
                dst_addr_mode = 1  # AddrMode.group
            elif addr_ieee in self._devices:
                dst_addr_mode = 2  # AddrMode.short
            else:
                dst_addr_mode = 0  # AddrMode.bound
        else:
            dst_addr_mode = 3  # AddrMode.ieee
        return dst_addr_mode

    def _bind_unbind(self, cmd, ieee, endpoint, cluster,
                     dst_addr=None, dst_endpoint=1):
        '''
        bind
        if dst_addr not specified, supposed zigate
        '''
        if not dst_addr:
            dst_addr = self.ieee
        dst_addr_fmt = 'H'
        dst_addr_mode = self._choose_addr_mode(dst_addr)
        if dst_addr_mode == 3:
            dst_addr_fmt = 'Q'
        ieee = self.__addr(ieee)
        dst_addr = self.__addr(dst_addr)
        data = struct.pack('!QBHB' + dst_addr_fmt + 'B', ieee, endpoint,
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
            ieee = self._devices[addr].ieee
            if ieee:
                return self.bind(ieee, endpoint, cluster, dst_addr, dst_endpoint)
            LOGGER.error('Failed to bind, addr {}, IEEE is missing'.format(addr))
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

    def network_address_request(self, ieee):
        ''' network address request '''
        target_addr = self.__addr('0000')
        ieee = self.__addr(ieee)
        data = struct.pack('!HQBB', target_addr, ieee, 0, 0)
        r = self.send_data(0x0040, data, wait_response=0x8040)
        if r:
            return r.data['addr']

    def ieee_address_request(self, addr):
        ''' ieee address request '''
        target_addr = self.__addr('0000')
        addr = self.__addr(addr)
        data = struct.pack('!HHBB', target_addr, addr, 0, 0)
        r = self.send_data(0x0041, data, wait_response=0x8041)
        if r:
            return r.data['ieee']

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

    def leave_request(self, addr, ieee=None, rejoin=False,
                      remove_children=False):
        '''
        Management Leave request
        rejoin : 0 do not rejoin, 1 rejoin
        remove_children : 0 Leave, do not remove children
                            1 = Leave, removing children
        '''
        addr = self.__addr(addr)
        if not ieee:
            ieee = self._devices[addr]['ieee']
        ieee = self.__addr(ieee)
        data = struct.pack('!HQBB', addr, ieee, rejoin, remove_children)
        return self.send_data(0x0047, data)

    def lqi_request(self, addr='0000', index=0, wait=False):
        '''
        Management LQI request
        '''
        addr = self.__addr(addr)
        data = struct.pack('!HB', addr, index)
        wait_response = None
        if wait:
            wait_response = 0x804e
        r = self.send_data(0x004e, data, wait_response=wait_response)
        return r

    def build_neighbours_table(self):
        '''
        Build neighbours table
        '''
        return self._neighbours_table(self.addr)

    def _neighbours_table(self, addr, nodes=None):
        '''
        Build neighbours table
        '''
        if nodes is None:
            nodes = []
        LOGGER.debug('Search for children of {}'.format(addr))
        nodes.append(addr)
        index = 0
        neighbours = []
        entries = 255
        while index < entries:
            r = self.lqi_request(addr, index, True)
            if not r:
                LOGGER.error('Failed to build neighbours table')
                return
            data = r.cleaned_data()
            entries = data['entries']
            for n in data['neighbours']:
                # bit_field
                # bit 0-1 = u2RxOnWhenIdle 0/1
                # bit 2-3 = u2Relationship 0/1/2
                # bit 4-5 = u2PermitJoining 0/1
                # bit 6-7 = u2DeviceType 0/1/2
                is_parent = n['bit_field'][2:4] == '00'
                is_child = n['bit_field'][2:4] == '01'
                is_router = n['bit_field'][6:8] == '01'
                if is_parent:
                    neighbours.append((n['addr'], addr, n['lqi']))
                elif is_child:
                    neighbours.append((addr, n['addr'], n['lqi']))
                elif n['depth'] == 0:
                    neighbours.append((self.addr, n['addr'], n['lqi']))
                if is_router and n['addr'] not in nodes:
                    LOGGER.debug('{} is a router, search for children'.format(n['addr']))
                    n2 = self._neighbours_table(n['addr'], nodes)
                    if n2:
                        neighbours += n2
            index += data['count']
        return neighbours

    def refresh_device(self, addr):
        '''
        convenient function to refresh device attribute
        '''
        device = self.get_device_from_addr(addr)
        if not device:
            return
        device.refresh_device()

    def discover_device(self, addr, force=False):
        '''
        starts discovery process
        '''
        LOGGER.debug('discover_device {}'.format(addr))
        device = self.get_device_from_addr(addr)
        if not device:
            return
        if force:
            device.discovery = ''
        if device.discovery:
            return
        typ = device.get_type()
        if typ:
            LOGGER.debug('Found type')
            if device.has_template():
                LOGGER.debug('Found template, loading it')
                device.load_template()
                return
        if 'mac_capability' not in device.info:
            LOGGER.debug('no mac_capability')
            self.node_descriptor_request(addr)
            return
        if not device.endpoints:
            LOGGER.debug('no endpoints')
            self.active_endpoint_request(addr)
            return
        if not typ:
            return
        if not device.load_template():
            LOGGER.debug('Loading template failed, tag as auto-discovered')
            device.discovery = 'auto-discovered'
            for endpoint, values in device.endpoints.items():
                for cluster in values.get('in_clusters', []):
                    self.attribute_discovery_request(addr, endpoint, cluster)

    def _generate_addr(self):
        addr = None
        while not addr or addr in self._devices or addr in self._groups:
            addr = random.randint(1, 0xffff)
        return addr

    @property
    def groups(self):
        '''
        return known groups
        '''
        return self._groups

    def get_group_for_addr(self, addr):
        '''
        return group for device addr
        '''
        groups = {}
        for group, members in self._groups.items():
            for member in members:
                if member[0] == addr:
                    if member[1] not in groups:
                        groups[member[1]] = []
                    groups[member[1]].append(group)
                    continue
        return groups

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
        if r.status == 0:
            self.__add_group(group_addr, self.__haddr(addr), endpoint)
        return group_addr

    def __add_group(self, group, addr, endpoint):
        if group not in self._groups:
            self._groups[group] = set()
        self._groups[group].add((addr, endpoint))

    def __remove_group(self, group, addr, endpoint):
        '''
        remove group for specified addr, endpoint
        if group is None,
            remove all group for specified addr, endpoint
        '''
        if group is None:
            groups = list(self._groups.keys())
        else:
            groups = [group]
        for group in groups:
            if (addr, endpoint) in self._groups.get(group, set()):
                self._groups[group].remove((addr, endpoint))
            if group in self._groups and len(self._groups[group]) == 0:
                del self._groups[group]

    def _sync_group_membership(self, addr, endpoint, groups):
        for group in groups:
            self.__add_group(group, addr, endpoint)
        to_remove = []
        for group in self._groups:
            if group not in groups:
                to_remove.append(group)
        for group in to_remove:
            self.__remove_group(group, addr, endpoint)

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

    def get_group_membership(self, addr, endpoint, groups=[]):
        '''
        Get group membership
        groups is list of group addr
        if empty get all groups
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        src_endpoint = 1
        length = len(groups)
        groups = [self.__addr(group) for group in groups]
        data = struct.pack('!BHBBB{}H'.format(length), addr_mode, addr,
                           src_endpoint, endpoint, length, *groups)
        return self.send_data(0x0062, data)

    def remove_group(self, addr, endpoint, group=None):
        '''
        Remove group
        if group not specified, remove all groups
        '''
        addr_mode = 2
        addr = self.__addr(addr)
        src_endpoint = 1
        group_addr = group
        if group is None:
            data = struct.pack('!BHBB', addr_mode, addr,
                               src_endpoint, endpoint)
            r = self.send_data(0x0064, data)
        else:
            group = self.__addr(group)
            data = struct.pack('!BHBBH', addr_mode, addr,
                               src_endpoint, endpoint, group)
            r = self.send_data(0x0063, data)
        if r.status == 0:
            self.__remove_group(group_addr, self.__haddr(addr), endpoint)
        return r

    def identify_device(self, addr, time_sec=5):
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

    def view_scene(self, addr, endpoint, group, scene):
        '''
        View scene
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        data = struct.pack('!BHBBHB', 2, addr, 1, endpoint, group, scene)
        return self.send_data(0x00A0, data)

    def add_scene(self, addr, endpoint, group, scene, name, transition=0):
        '''
        Add scene
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        data = struct.pack('!BHBBHB', 2, addr, 1, endpoint, group, scene)
        return self.send_data(0x00A1, data)

    def remove_scene(self, addr, endpoint, group, scene=None):
        '''
        Remove scene
        if scene is not specified, remove all scenes
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        if scene is None:
            data = struct.pack('!BHBBH', 2, addr, 1, endpoint, group)
            return self.send_data(0x00A3, data)
        data = struct.pack('!BHBBHB', 2, addr, 1, endpoint, group, scene)
        return self.send_data(0x00A2, data)

    def store_scene(self, addr, endpoint, group, scene):
        '''
        Store scene
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        data = struct.pack('!BHBBHB', 2, addr, 1, endpoint, group, scene)
        return self.send_data(0x00A4, data)

    def recall_scene(self, addr, endpoint, group, scene):
        '''
        Store scene
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        data = struct.pack('!BHBBHB', 2, addr, 1, endpoint, group, scene)
        return self.send_data(0x00A5, data)

    def scene_membership_request(self, addr, endpoint, group):
        '''
        Scene Membership request
        '''
        addr = self.__addr(addr)
        group = self.__addr(group)
        data = struct.pack('!BHBBH', 2, addr, 1, endpoint, group)
        return self.send_data(0x00A6, data)

    def copy_scene(self, addr, endpoint, from_group, from_scene, to_group, to_scene):
        '''
        Copy scene
        '''
        addr = self.__addr(addr)
        from_group = self.__addr(from_group)
        to_group = self.__addr(to_group)
        data = struct.pack('!BHBBBHBHB', 2, addr, 1, endpoint, 0,
                           from_group, from_scene,
                           to_group, to_scene)
        return self.send_data(0x00A9, data)

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

    def identify_trigger_effect(self, addr, endpoint, effect="blink"):
        '''
        identify_trigger_effect

        effects available:
        - blink: Light is switched on and then off (once)
        - breathe: Light is switched on and off by smoothly increasing and then
                   decreasing its brightness over a one-second period, and then this is repeated 15 times
        - okay: Colour light goes green for one second. Monochrome light flashes twice in one second.
        - channel_change: Colour light goes orange for 8 seconds. Monochrome light switches to
                          maximum brightness for 0.5 s and then to minimum brightness for 7.5 s
        - finish_effect: Current stage of effect is completed and then identification mode is
                         terminated (e.g. for the Breathe effect, only the current one-second cycle will be completed)
        - Stop effect: Current effect and identification mode are terminated as soon as possible
        '''
        effects = {
            'blink': 0x00,
            'breathe': 0x01,
            'okay': 0x02,
            'channel_change': 0x0b,
            'finish_effect': 0xfe,
            'stop_effect': 0xff
        }
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        if effect not in effects.keys():
            effect = 'blink'
        effect_variant = 0  # Current Zigbee standard doesn't provide any variant
        data = struct.pack('!BHBBBB', addr_mode, addr, 1, endpoint, effects[effect], effect_variant)
        return self.send_data(0x00E0, data)

    def read_attribute_request(self, addr, endpoint, cluster, attributes,
                               direction=0, manufacturer_code=0):
        '''
        Read Attribute request
        attribute can be a unique int or a list of int
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        if not isinstance(attributes, list):
            attributes = [attributes]
        length = len(attributes)
        manufacturer_specific = manufacturer_code != 0
        for i in range(0, length, 10):
            sub_attributes = attributes[i: i + 10]
            sub_length = len(sub_attributes)
            data = struct.pack('!BHBBHBBHB{}H'.format(sub_length), addr_mode, addr, 1,
                               endpoint, cluster,
                               direction, manufacturer_specific,
                               manufacturer_code, sub_length, *sub_attributes)
            self.send_data(0x0100, data)

    def write_attribute_request(self, addr, endpoint, cluster, attributes,
                                direction=0, manufacturer_code=0):
        '''
        Write Attribute request
        attribute could be a tuple of (attribute_id, attribute_type, data)
        or a list of tuple (attribute_id, attribute_type, data)
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        fmt = ''
        if not isinstance(attributes, list):
            attributes = [attributes]
        attributes_data = []
        for attribute_tuple in attributes:
            data_type = DATA_TYPE[attribute_tuple[1]]
            fmt += 'HB' + data_type
            attributes_data += attribute_tuple
        length = len(attributes)
        manufacturer_specific = manufacturer_code != 0
        data = struct.pack('!BHBBHBBHB{}'.format(fmt), addr_mode, addr, 1,
                           endpoint, cluster,
                           direction, manufacturer_specific,
                           manufacturer_code, length, *attributes_data)
        self.send_data(0x0110, data)

    def reporting_request(self, addr, endpoint, cluster, attributes,
                          direction=0, manufacturer_code=0, min_interval=1, max_interval=3600):
        '''
        Configure reporting request
        attribute could be a tuple of (attribute_id, attribute_type)
        or a list of tuple (attribute_id, attribute_type)
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        if not isinstance(attributes, list):
            attributes = [attributes]
        length = len(attributes)

        attribute_direction = 0
        timeout = 0
        change = 0
        fmt = ''
        attributes_data = []
        for attribute_tuple in attributes:
            fmt += 'BBHHHHB'
            attributes_data += [attribute_direction,
                                attribute_tuple[1],
                                attribute_tuple[0],
                                min_interval,
                                max_interval,
                                timeout,
                                change
                                ]
        manufacturer_specific = manufacturer_code != 0
        data = struct.pack('!BHBBHBBHB{}'.format(fmt), addr_mode, addr, 1, endpoint, cluster,
                           direction, manufacturer_specific,
                           manufacturer_code, length, *attributes_data)
        r = self.send_data(0x0120, data, 0x8120)
        # reporting not supported on cluster 6, supposed on/off attribute
        if r and r.status == 0x8c and r.cluster == 6:
            device = self._devices[r.addr]
            device.set_assumed_state()
        return r

    def ota_load_image(self, path_to_file):
        # Check that ota process is not active
        if self._ota['active'] is True:
            LOGGER.error('Cannot load image while OTA process is active.')
            self.get_ota_status()
            return

        # Try reading file from user provided path
        try:
            with open(path_to_file, 'rb') as f:
                ota_file_content = f.read()
        except OSError as err:
            LOGGER.error('{path}: {error}'.format(path=path_to_file, error=err))
            return False

        # Ensure that file has 69 bytes so it can contain header
        if len(ota_file_content) < 69:
            LOGGER.error('OTA file is too short')
            return False

        # Read header data
        try:
            header_data = list(struct.unpack('<LHHHHHLH32BLBQHH', ota_file_content[:69]))
        except struct.error:
            LOGGER.exception('Header is not correct')
            return False

        # Fix header str
        # First replace null characters from header str to spaces
        for i in range(8, 40):
            if header_data[i] == 0x00:
                header_data[i] = 0x20
        # Reconstruct header data
        header_data_compact = header_data[0:8] + [header_data[8:40]] + header_data[40:]
        # Convert header data to dict
        header_headers = [
            'file_id', 'header_version', 'header_length', 'header_fctl', 'manufacturer_code', 'image_type',
            'image_version', 'stack_version', 'header_str', 'size', 'security_cred_version', 'upgrade_file_dest',
            'min_hw_version', 'max_hw_version'
        ]
        header = dict(zip(header_headers, header_data_compact))

        # Check that size from header corresponds to file size
        if header['size'] != len(ota_file_content):
            LOGGER.error('Header size({header}) and file size({file}) does not match'.format(
                header=header['size'], file=len(ota_file_content)
            ))
            return False

        destination_address_mode = 0x02
        destination_address = 0x0000
        data = struct.pack('!BHlHHHHHLH32BLBQHH', destination_address_mode, destination_address, *header_data)
        response = self.send_data(0x0500, data)

        # If response is success place header and file content to variable
        if response.status == 0:
            LOGGER.info('OTA header loaded to server successfully.')
            self._ota_reset_local_variables()
            self._ota['image']['header'] = header
            self._ota['image']['data'] = ota_file_content
        else:
            LOGGER.warning('Something wrong with ota file header.')

    def _ota_send_image_data(self, request):
        errors = False
        # Ensure that image is loaded using ota_load_image
        if self._ota['image']['header'] is None:
            LOGGER.error('No header found. Load image using ota_load_image(\'path_to_ota_image\')')
            errors = True
        if self._ota['image']['data'] is None:
            LOGGER.error('No data found. Load image using ota_load_image(\'path_to_ota_ota\')')
            errors = True
        if errors:
            return

        # Compare received image data to loaded image
        errors = False
        if request['image_version'] != self._ota['image']['header']['image_version']:
            LOGGER.error('Image versions do not match. Make sure you have correct image loaded.')
            errors = True
        if request['image_type'] != self._ota['image']['header']['image_type']:
            LOGGER.error('Image types do not match. Make sure you have correct image loaded.')
            errors = True
        if request['manufacturer_code'] != self._ota['image']['header']['manufacturer_code']:
            LOGGER.error('Manufacturer codes do not match. Make sure you have correct image loaded.')
            errors = True
        if errors:
            return

        # Mark ota process started
        if self._ota['starttime'] is False and self._ota['active'] is False:
            self._ota['starttime'] = datetime.datetime.now()
            self._ota['active'] = True
            self._ota['transfered'] = 0
            self._ota['addr'] = request['addr']

        source_endpoint = 0x01
        ota_status = 0x00  # Success. Using value 0x01 would make client to request data again later

        # Get requested bytes from ota file
        self._ota['transfered'] = request['file_offset']
        end_position = request['file_offset'] + request['max_data_size']
        ota_data_to_send = self._ota['image']['data'][request['file_offset']:end_position]
        data_size = len(ota_data_to_send)
        ota_data_to_send = struct.unpack('<{}B'.format(data_size), ota_data_to_send)

        # Giving user feedback of ota process
        self.get_ota_status(debug=True)

        data = struct.pack('!BHBBBBLLHHB{}B'.format(data_size), request['address_mode'], self.__addr(request['addr']),
                           source_endpoint, request['endpoint'], request['sequence'], ota_status,
                           request['file_offset'], self._ota['image']['header']['image_version'],
                           self._ota['image']['header']['image_type'],
                           self._ota['image']['header']['manufacturer_code'],
                           data_size, *ota_data_to_send)
        self.send_data(0x0502, data, wait_status=False)

    def _ota_handle_upgrade_end_request(self, request):
        if self._ota['active'] is True:
            # Handle error statuses
            if request['status'] == 0x00:
                LOGGER.info('OTA image upload finnished successfully in {seconds}s.'.format(
                    seconds=(datetime.datetime.now() - self._ota['starttime']).seconds))
            elif request['status'] == 0x95:
                LOGGER.warning('OTA aborted by client')
            elif request['status'] == 0x96:
                LOGGER.warning('OTA image upload successfully, but image verification failed.')
            elif request['status'] == 0x99:
                LOGGER.warning('OTA image uploaded successfully, but client needs more images for update.')
            elif request['status'] != 0x00:
                LOGGER.warning('Some unexpected OTA status {}'.format(request['status']))
            # Reset local ota variables
            self._ota_reset_local_variables()

    def _ota_reset_local_variables(self):
        self._ota = {
            'image': {
                'header': None,
                'data': None,
            },
            'active': False,
            'starttime': False,
            'transfered': 0,
            'addr': None
        }

    def get_ota_status(self, debug=False):
        if self._ota['active']:
            image_size = len(self._ota['image']['data'])
            time_passed = (datetime.datetime.now() - self._ota['starttime']).seconds
            try:
                time_remaining = int((image_size / self._ota['transfered']) * time_passed) - time_passed
            except ZeroDivisionError:
                time_remaining = -1
            message = 'OTA upgrade address {addr}: {sent:>{width}}/{total:>{width}} {percentage:.3%}'.format(
                addr=self._ota['addr'], sent=self._ota['transfered'], total=image_size,
                percentage=self._ota['transfered'] / image_size, width=len(str(image_size)))
            message += ' time elapsed: {passed}s Time remaining estimate: {remaining}s'.format(
                passed=time_passed, remaining=time_remaining
            )
        else:
            message = "OTA process is not active"
        if debug:
            LOGGER.debug(message)
        else:
            LOGGER.info(message)

    def ota_image_notify(self, addr, destination_endpoint=0x01, payload_type=0):
        """
        Send image available notification to client. This will start ota process

        :param addr:
        :param destination_endpoint:
        :param payload_type: 0, 1, 2, 3
        :type payload_type: int
        :return:
        """
        # Get required data from ota header
        if self._ota['image']['header'] is None:
            LOGGER.warning('Cannot read ota header. No ota file loaded.')
            return False
        image_version = self._ota['image']['header']['image_version']
        image_type = self._ota['image']['header']['image_type']
        manufacturer_code = self._ota['image']['header']['manufacturer_code']

        source_endpoint = 0x01
        destination_address_mode = 0x02  # uint16
        destination_address = self.__addr(addr)
        query_jitter = 100

        if payload_type == 0:
            image_version = 0xFFFFFFFF
            image_type = 0xFFFF
            manufacturer_code = 0xFFFF
        elif payload_type == 1:
            image_version = 0xFFFFFFFF
            image_type = 0xFFFF
        elif payload_type == 2:
            image_version = 0xFFFFFFFF

        data = struct.pack('!BHBBBLHHB', destination_address_mode, destination_address,
                           source_endpoint, destination_endpoint, 0,
                           image_version, image_type, manufacturer_code, query_jitter)
        self.send_data(0x0505, data)

    def attribute_discovery_request(self, addr, endpoint, cluster,
                                    direction=0, manufacturer_code=0):
        '''
        Attribute discovery request
        '''
        addr = self.__addr(addr)
        manufacturer_specific = manufacturer_code != 0
        data = struct.pack('!BHBBHHBBHB', 2, addr, 1, endpoint, cluster,
                           0, direction, manufacturer_specific,
                           manufacturer_code, 255)
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
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBB', addr_mode, addr, 1, endpoint, onoff)
        cmd = 0x0092
        if on_time or off_time:
            cmd = 0x0093
            data += struct.pack('!HH', on_time, off_time)
        elif effect:
            cmd = 0x0094
            data = struct.pack('!BHBBBB', addr_mode, addr, 1, endpoint, effect, gradient)
        return self.send_data(cmd, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_level(self, addr, endpoint, onoff=OFF, mode=0, rate=0):
        '''
        move to level
        mode 0 up, 1 down
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBBBB', addr_mode, addr, 1, endpoint, onoff, mode, rate)
        return self.send_data(0x0080, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_level_onoff(self, addr, endpoint, onoff=OFF, level=0, transition_time=0):
        '''
        move to level with on off
        level between 0 - 100
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        level = int(level * 254 // 100)
        data = struct.pack('!BHBBBBH', addr_mode, addr, 1, endpoint, onoff, level, transition_time)
        return self.send_data(0x0081, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_step(self, addr, endpoint, onoff=OFF, step_mode=0, step_size=0, transition_time=0):
        '''
        move step
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBBBBH', addr_mode, addr, 1, endpoint, onoff, step_mode, step_size, transition_time)
        return self.send_data(0x0082, data)

    @register_actions(ACTIONS_LEVEL)
    def action_move_stop_onoff(self, addr, endpoint, onoff=OFF):
        '''
        move stop on off
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBB', addr_mode, addr, 1, endpoint, onoff)
        return self.send_data(0x0084, data)

    @register_actions(ACTIONS_HUE)
    def action_move_hue(self, addr, endpoint, hue, direction=0, transition=0):
        '''
        move to hue
        hue 0-360 in degrees
        direction : 0 shortest, 1 longest, 2 up, 3 down
        transition in second
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        hue = int(hue * 254 // 360)
        data = struct.pack('!BHBBBBH', addr_mode, addr, 1, endpoint,
                           hue, direction, transition)
        return self.send_data(0x00B0, data)

    @register_actions(ACTIONS_HUE)
    def action_move_hue_saturation(self, addr, endpoint, hue, saturation=100, transition=0):
        '''
        move to hue and saturation
        hue 0-360 in degrees
        saturation 0-100 in percent
        transition in second
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        hue = int(hue * 254 // 360)
        saturation = int(saturation * 254 // 100)
        data = struct.pack('!BHBBBBH', addr_mode, addr, 1, endpoint,
                           hue, saturation, transition)
        return self.send_data(0x00B6, data)

    @register_actions(ACTIONS_HUE)
    def action_move_hue_hex(self, addr, endpoint, color_hex, transition=0):
        '''
        move to hue color in #ffffff
        transition in second
        '''
        rgb = hex_to_rgb(color_hex)
        return self.action_move_hue_rgb(addr, endpoint, rgb, transition)

    @register_actions(ACTIONS_HUE)
    def action_move_hue_rgb(self, addr, endpoint, rgb, transition=0):
        '''
        move to hue (r,g,b) example : (1.0, 1.0, 1.0)
        transition in second
        '''
        hue, saturation, level = colorsys.rgb_to_hsv(*rgb)
        hue = int(hue * 360)
        saturation = int(saturation * 100)
        level = int(level * 100)
        self.action_move_level_onoff(addr, endpoint, ON, level, 0)
        return self.action_move_hue_saturation(addr, endpoint, hue, saturation, transition)

    @register_actions(ACTIONS_COLOR)
    def action_move_colour(self, addr, endpoint, x, y, transition=0):
        '''
        move to colour x y
        x, y can be integer 0-65536 or float 0-1.0
        transition in second
        '''
        if isinstance(x, float) and x <= 1:
            x = int(x * 65536)
        if isinstance(y, float) and y <= 1:
            y = int(y * 65536)
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBHHH', addr_mode, addr, 1, endpoint,
                           x, y, transition)
        return self.send_data(0x00B7, data)

    @register_actions(ACTIONS_COLOR)
    def action_move_colour_hex(self, addr, endpoint, color_hex, transition=0):
        '''
        move to colour #ffffff
        convenient function to set color in hex format
        transition in second
        '''
        x, y = hex_to_xy(color_hex)
        return self.action_move_colour(addr, endpoint, x, y, transition)

    @register_actions(ACTIONS_COLOR)
    def action_move_colour_rgb(self, addr, endpoint, rgb, transition=0):
        '''
        move to colour (r,g,b) example : (1.0, 1.0, 1.0)
        convenient function to set color in hex format
        transition in second
        '''
        x, y = rgb_to_xy(rgb)
        return self.action_move_colour(addr, endpoint, x, y, transition)

    @register_actions(ACTIONS_TEMPERATURE)
    def action_move_temperature(self, addr, endpoint, mired, transition=0):
        '''
        move colour to temperature
        mired color temperature
        transition in second
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBHH', addr_mode, addr, 1, endpoint,
                           mired, transition)
        return self.send_data(0x00C0, data)

    @register_actions(ACTIONS_TEMPERATURE)
    def action_move_temperature_kelvin(self, addr, endpoint, temperature, transition=0):
        '''
        move colour to temperature
        temperature unit is kelvin
        transition in second
        convenient function to use kelvin instead of mired
        '''
        temperature = int(1000000 // temperature)
        return self.action_move_temperature(addr, endpoint, temperature, transition)

    @register_actions(ACTIONS_TEMPERATURE)
    def action_move_temperature_rate(self, addr, endpoint, mode, rate, min_mired, max_mired):
        '''
        move colour temperature in specified rate towards given min or max value
        Available modes:
         - 0: Stop
         - 1: Increase
         - 3: Decrease
        rate: how many temperature units are moved in one second
        min_mired: Minium temperature where decreasing stops in mired
        max_mired: Maxium temperature where increasing stops in mired
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBBHHH', addr_mode, addr, 1, endpoint, mode, rate, min_mired, max_mired)
        return self.send_data(0x00C1, data)

    @register_actions(ACTIONS_LOCK)
    def action_lock(self, addr, endpoint, lock):
        '''
        Lock / unlock
        '''
        addr_mode = self._choose_addr_mode(addr)
        addr = self.__addr(addr)
        data = struct.pack('!BHBBB', addr_mode, addr, 1, endpoint, lock)
        return self.send_data(0x00f0, data)

    @register_actions(ACTIONS_COVER)
    def action_cover(self, addr, endpoint, cmd, param=None):
        '''
        Open, close, move, ...
        cmd could be :
            OPEN = 0x00
            CLOSE = 0x01
            STOP = 0x02
            LIFT_VALUE = 0x04
            LIFT_PERCENT = 0x05
            TILT_VALUE = 0x07
            TILT_PERCENT = 0x08
        '''
        addr_mode = self._choose_addr_mode(addr)
        fmt = '!BHBBB'
        addr = self.__addr(addr)
        args = [addr_mode, addr, 1, endpoint, cmd]
        if cmd in (0x04, 0x07):
            fmt += 'H'
            args.append(param)
        elif cmd in (0x05, 0x08):
            fmt += 'B'
            args.append(param)
        data = struct.pack(fmt, *args)
        return self.send_data(0x00fa, data)

    def raw_aps_data_request(self, addr, src_ep, dst_ep, profile, cluster, payload, addr_mode=2, security=0):
        '''
        Send raw APS Data request
        '''
        addr = self.__addr(addr)
        length = len(payload)
        radius = 0
        data = struct.pack('!BHBBHHBBB{}s'.format(length), addr_mode, addr, src_ep, dst_ep,
                           cluster, profile, security, radius, length, payload)
        return self.send_data(0x0530, data)

    def set_TX_power(self, percent=100):
        '''
        Set TX Power between 0-100%
        '''
        percent = percent * 255 // 100
        data = struct.pack('!B', percent)
        return self.send_data(0x0806, data)

    def start_mqtt_broker(self, host='localhost:1883', username=None, password=None):
        '''
        Start a MQTT broker in a new thread
        '''
        from .mqtt_broker import MQTT_Broker
        broker = MQTT_Broker(self, host, username, password)
        broker.connect()
        self.broker_thread = threading.Thread(target=broker.client.loop_forever,
                                              name='ZiGate-MQTT')
        self.broker_thread.setDaemon(True)
        self.broker_thread.start()

    def generate_templates(self, dirname='~'):
        '''
        Generate template file for each device
        '''
        for device in self._devices.values():
            device.generate_template(dirname)


class FakeZiGate(ZiGate):
    '''
    Fake ZiGate for test only without real hardware
    '''
    def __init__(self, port='auto', path='~/.zigate.json',
                 auto_start=False, auto_save=False, channel=None, adminpanel=False):
        ZiGate.__init__(self, port=port, path=path, auto_start=auto_start, auto_save=auto_save,
                        channel=channel, adminpanel=adminpanel)
        self._addr = '0000'
        self._ieee = '0123456789abcdef'
        # by default add a fake xiaomi temp sensor on address abcd
        device = Device({'addr': 'abcd', 'ieee': '0123456789abcdef'}, self)
        device.set_attribute(1, 0, {'attribute': 5, 'lqi': 170, 'data': 'lumi.weather'})
        device.load_template()
        self._devices['abcd'] = device

    def startup(self, channel=None):
        ZiGate.startup(self, channel=channel)
        self.connection.start_fake_response()

    def setup_connection(self):
        self.connection = FakeTransport()


class ZiGateGPIO(ZiGate):
    def __init__(self, port='auto', path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True,
                 channel=None,
                 adminpanel=False):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(13, GPIO.OUT)  # GPIO2
        self.set_running_mode()
        ZiGate.__init__(self, port=port, path=path, auto_start=auto_start,
                        auto_save=auto_save, channel=channel, adminpanel=adminpanel)

    def set_running_mode(self):
        GPIO.output(13, GPIO.HIGH)  # GPIO2
        GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # GPIO0
        sleep(0.5)
        GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # GPIO0
        sleep(0.5)

    def set_bootloader_mode(self):
        GPIO.output(13, GPIO.LOW)  # GPIO2
        GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # GPIO0
        sleep(0.5)
        GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # GPIO0
        sleep(0.5)

    def flash_firmware(self, path, erase_eeprom=False):
        from .flasher import flash
        self.set_bootloader_mode()
        flash(self._port, write=path, erase=erase_eeprom)
        self.set_running_mode()

    def __del__(self):
        GPIO.cleanup()
        ZiGate.__del__(self)

    def setup_connection(self):
        self.connection = ThreadSerialConnection(self, self._port, '3f201')


class ZiGateWiFi(ZiGate):
    def __init__(self, host, port=None, path='~/.zigate.json',
                 auto_start=True,
                 auto_save=True,
                 channel=None,
                 adminpanel=False):
        self._host = host
        ZiGate.__init__(self, port=port, path=path,
                        auto_start=auto_start,
                        auto_save=auto_save,
                        channel=channel,
                        adminpanel=adminpanel
                        )

    def setup_connection(self):
        self.connection = ThreadSocketConnection(self, self._host, self._port)

    def reboot(self):
        '''
        ask zigate wifi to reboot
        '''
        import requests
        requests.get('http://{}/reboot'.format(self._host))


class DeviceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Device):
            return obj.to_json()
        if isinstance(obj, Cluster):
            return obj.to_json()
        elif isinstance(obj, bytes):
            return hexlify(obj).decode()
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, type):
            return obj.__name__
        return json.JSONEncoder.default(self, obj)


class Device(object):
    def __init__(self, info=None, zigate_instance=None):
        self._zigate = zigate_instance
        self._lock = threading.Lock()
        self.info = info or {}
        self.endpoints = {}
        self._expire_timer = {}
        self.missing = False
        self.genericType = ''
        self.discovery = ''

    def _lock_acquire(self):
        r = self._lock.acquire(True, 5)
        if not r:
            LOGGER.error('Failed to acquire Lock on device {}'.format(self))

    def _lock_release(self):
        if not self._lock.locked():
            LOGGER.error('Device Lock not locked for device {} !'.format(self))
        else:
            self._lock.release()

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
                        actions[ep_id].append(ACTIONS_ONOFF)
                    if 0x0008 in endpoint['in_clusters'] and endpoint['device'] != 0x010a:
                        # except device 0x010a because Tradfri Outlet don't have level control
                        # but still have endpoint 8...
                        actions[ep_id].append(ACTIONS_LEVEL)
                    if 0x0101 in endpoint['in_clusters']:
                        actions[ep_id].append(ACTIONS_LOCK)
                    if 0x0102 in endpoint['in_clusters']:
                        actions[ep_id].append(ACTIONS_COVER)
                    if 0x0300 in endpoint['in_clusters']:
                        # if endpoint['device'] in (0x0102, 0x0105):
                        if endpoint['device'] in (0x0105,):
                            actions[ep_id].append(ACTIONS_HUE)
                        elif endpoint['device'] in (0x010D, 0x0210):
                            actions[ep_id].append(ACTIONS_COLOR)
                            actions[ep_id].append(ACTIONS_HUE)
                            actions[ep_id].append(ACTIONS_TEMPERATURE)
                        elif endpoint['device'] in (0x0102, 0x010C, 0x0220):
                            actions[ep_id].append(ACTIONS_TEMPERATURE)
                        else:  # 0x0200
                            actions[ep_id].append(ACTIONS_COLOR)
                            actions[ep_id].append(ACTIONS_HUE)
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
        automatically bind and report data
        '''
        if not BIND_REPORT:
            return
        if enpoint_id:
            endpoints_list = [(enpoint_id, self.endpoints[enpoint_id])]
        else:
            endpoints_list = list(self.endpoints.items())
        LOGGER.debug('Start automagic bind and report process for device {}'.format(self))
        for endpoint_id, endpoint in endpoints_list:
            # if endpoint['device'] in ACTUATORS:  # light
            LOGGER.debug('Bind and report endpoint {} for device {}'.format(endpoint_id, self))
            if 0x0001 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0001')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0001)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0001, (0x0020, 0x20))
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0001, (0x0021, 0x20))
            if 0x0006 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0006')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0006)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0006, (0x0000, 0x10))
            if 0x0008 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0008')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0008)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0008, (0x0000, 0x20))
            if 0x000f in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x000f')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x000f)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x000f, (0x0055, 0x10))
            if 0x0102 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0102')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0102)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0102, (0x0007, 0x20))
            if 0x0201 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0201')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0201)
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0201, (0x0000, 0x29))
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0201, (0x0008, 0x20))
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0201, (0x0012, 0x29))
                self._zigate.reporting_request(self.addr, endpoint_id,
                                               0x0201, (0x001C, 0x30))
            if 0x0300 in endpoint['in_clusters']:
                LOGGER.debug('bind and report for cluster 0x0300')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0300)
                if endpoint['device'] in (0x0105,):
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0000, 0x20))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0001, 0x20))
                elif endpoint['device'] in (0x010D, 0x0210):
                    # self._zigate.reporting_request(self.addr,
                    #                               endpoint_id,
                    #                               0x0300, [(0x0000, 0x20),
                    #                                        (0x0001, 0x20),
                    #                                        (0x0003, 0x21),
                    #                                        (0x0004, 0x21),
                    #                                        (0x0007, 0x21),
                    #                                        ])
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0000, 0x20))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0001, 0x20))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0003, 0x21))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0004, 0x21))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0007, 0x21))
                elif endpoint['device'] in (0x0102, 0x010C, 0x0220):
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0007, 0x21))
                else:  # 0x0200
                    # self._zigate.reporting_request(self.addr,
                    #                               endpoint_id,
                    #                               0x0300, [(0x0000, 0x20),
                    #                                        (0x0001, 0x20),
                    #                                        (0x0003, 0x21),
                    #                                        (0x0004, 0x21),
                    #                                        ])
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0000, 0x20))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0001, 0x20))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0003, 0x21))
                    self._zigate.reporting_request(self.addr,
                                                   endpoint_id,
                                                   0x0300, (0x0004, 0x21))
            if 0xFC00 in endpoint['in_clusters']:
                LOGGER.debug('bind for cluster 0xFC00')
                self._zigate.bind_addr(self.addr, endpoint_id, 0xFC00)
            if 0x0702 in endpoint['in_clusters']:
                LOGGER.debug('bind for cluster 0x0702')
                self._zigate.bind_addr(self.addr, endpoint_id, 0x0702)
                self._zigate.reporting_request(self.addr,
                                               endpoint_id,
                                               0x0702, (0x0000, 0x25))

    @staticmethod
    def from_json(data, zigate_instance=None):
        d = Device(zigate_instance=zigate_instance)
        d.info = data.get('info', {})
        d.genericType = data.get('generictype', '')
        d.discovery = data.get('discovery', '')
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
                    cluster = Cluster.from_json(cl, endpoint, d)
                    endpoint['clusters'][cluster.cluster_id] = cluster
        if 'power_source' in d.info:  # old version
            d.info['power_type'] = d.info.pop('power_source')
        if 'manufacturer' in d.info:  # old version
            d.info['manufacturer_code'] = d.info.pop('manufacturer')
        if 'rssi' in d.info:  # old version
            d.info['lqi'] = d.info.pop('rssi')
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
             'generictype': self.genericType,
             'discovery': self.discovery
             }
        if properties:
            r['properties'] = list(self.properties)
        return r

    def __str__(self):
        name = self.get_property_value('type', '')
        manufacturer = self.get_property_value('manufacturer', 'Device')
        return '{} {} ({}) {}'.format(manufacturer, name, self.addr, self.ieee)

    def __repr__(self):
        return self.__str__()

    @property
    def addr(self):
        return self.info['addr']

    @property
    def ieee(self):
        ieee = self.info.get('ieee')
        if ieee is None:
            LOGGER.error('IEEE is missing for {}, please pair it again !'.format(self.addr))
        return ieee

    @property
    def rssi(self):  # compat
        return self.lqi

    @rssi.setter
    def rssi(self, value):  # compat
        self.lqi = value

    @property
    def lqi(self):
        return self.info.get('lqi', 0)

    @lqi.setter
    def lqi(self, value):
        self.info['lqi'] = value

    @property
    def last_seen(self):
        return self.info.get('last_seen')

    @property
    def battery_percent(self):
        percent = self.get_property_value('battery_percent')
        if not percent:
            percent = 100
            if self.info.get('power_type') == 0:
                power_source = self.get_property_value('power_source')
                if power_source is None:
                    power_source = 3
                battery_voltage = self.get_property_value('battery_voltage')
                if power_source == 3:  # battery
                    power_source = 3.1
                if power_source and battery_voltage:
                    power_end = 0.9 * power_source
                    percent = (battery_voltage - power_end) * 100 / (power_source - power_end)
                if percent > 100:
                    percent = 100
        return percent

    @property
    def rssi_percent(self):  # compat
        return self.lqi_percent

    @property
    def lqi_percent(self):
        return round(100 * self.lqi / 255)

    def get_type(self, wait=True):
        typ = self.get_value('type')
        if typ is None:
            for endpoint in self.endpoints:
                if 0 in self.endpoints[endpoint]['in_clusters'] or not self.endpoints[endpoint]['in_clusters']:
                    self._zigate.read_attribute_request(self.addr,
                                                        endpoint,
                                                        0x0000,
                                                        [0x0004, 0x0005]
                                                        )
                    if 0 in self.endpoints[endpoint]['in_clusters']:
                        break
            if not wait or not self.endpoints:
                return
            # wait for type
            t1 = time()
            while self.get_value('type') is None:
                sleep(0.01)
                t2 = time()
                if t2 - t1 > WAIT_TIMEOUT:
                    LOGGER.warning('No response waiting for type')
                    return
            typ = self.get_value('type')
        return typ

    def refresh_device(self):
        to_read = {}
        for attribute in self.attributes:
            k = (attribute['endpoint'], attribute['cluster'])
            if k not in to_read:
                to_read[k] = []
            to_read[k].append(attribute['attribute'])
        for k, attributes in to_read.items():
            endpoint, cluster = k
            self._zigate.read_attribute_request(self.addr,
                                                endpoint,
                                                cluster,
                                                attributes)

    def discover_device(self):
        self._zigate.discover_device(self.addr)

    def identify_device(self, time_sec=5):
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
        self._lock_acquire()
        self.info.update(device.info)
        self._merge_endpoints(device.endpoints)
        self.genericType = self.genericType or device.genericType
#         self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self._lock_release()

    def _merge_endpoints(self, endpoints):
        for endpoint_id, endpoint in endpoints.items():
            if endpoint_id not in self.endpoints:
                self.endpoints[endpoint_id] = endpoint
            else:
                myendpoint = self.endpoints[endpoint_id]
                if 'clusters' not in myendpoint:
                    myendpoint['clusters'] = {}
                myendpoint['profile'] = endpoint.get('profile') or myendpoint.get('profile', 0)
                myendpoint['device'] = endpoint.get('device') or myendpoint.get('device', 0)
                myendpoint['in_clusters'] = endpoint.get('in_clusters') or myendpoint.get('in_clusters', [])
                myendpoint['out_clusters'] = endpoint.get('out_clusters') or myendpoint.get('out_clusters', [])
                for cluster_id, cluster in endpoint['clusters'].items():
                    if cluster_id not in myendpoint['clusters']:
                        myendpoint['clusters'][cluster_id] = cluster
                    else:
                        mycluster = myendpoint['clusters'][cluster_id]
                        for attribute in cluster.attributes.values():
                            mycluster.update(attribute)

    def update_info(self, info):
        self._lock_acquire()
        self.info.update(info)
        self._lock_release()

    def get_endpoint(self, endpoint_id):
        self._lock_acquire()
        if endpoint_id not in self.endpoints:
            self.endpoints[endpoint_id] = {'clusters': {},
                                           'profile': 0,
                                           'device': 0,
                                           'in_clusters': [],
                                           'out_clusters': [],
                                           }
        self._lock_release()
        return self.endpoints[endpoint_id]

    def get_cluster(self, endpoint_id, cluster_id):
        endpoint = self.get_endpoint(endpoint_id)
        self._lock_acquire()
        if cluster_id not in endpoint['clusters']:
            cluster = get_cluster(cluster_id, endpoint, self)
            endpoint['clusters'][cluster_id] = cluster
        self._lock_release()
        return endpoint['clusters'][cluster_id]

    def set_attribute(self, endpoint_id, cluster_id, data):
        added = False
        lqi = data.pop('lqi', 0)
        if lqi > 0:
            self.info['lqi'] = lqi
        self.info['last_seen'] = strftime('%Y-%m-%d %H:%M:%S')
        self.missing = False
        cluster = self.get_cluster(endpoint_id, cluster_id)
        self._lock_acquire()
        r = cluster.update(data)
        if r:
            added, attribute = r
            if 'expire' in attribute:
                self._set_expire_timer(endpoint_id, cluster_id,
                                       attribute['attribute'],
                                       attribute['expire'])
        self._avoid_duplicate()
        self._lock_release()
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
            LOGGER.debug('Cancel previous Timer {}'.format(timer))
            timer.cancel()
        timer = threading.Timer(expire,
                                functools.partial(self._reset_attribute,
                                                  endpoint_id,
                                                  cluster_id,
                                                  attribute_id))
        timer.setDaemon(True)
        timer.start()
        self._expire_timer[k] = timer

    def _reset_attribute(self, endpoint_id, cluster_id, attribute_id):
        attribute = self.get_attribute(endpoint_id,
                                       cluster_id,
                                       attribute_id)
        value = attribute['value']
        if 'expire_value' in attribute:
            new_value = attribute['expire_value']
        elif 'type' in attribute:
            new_value = attribute['type']()
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

    def need_discovery(self):
        '''
        return True if device need to be discovered
        because of missing important information
        '''
        need = False
        LOGGER.debug('Check Need discovery {}'.format(self))
        if not self.discovery:
            self.load_template()
        if not self.get_property_value('type'):
            LOGGER.debug('Need discovery : no type')
            need = True
        if not self.ieee:
            LOGGER.debug('Need discovery : no IEEE')
            need = True
        if not self.endpoints:
            LOGGER.debug('Need discovery : no endpoints')
            need = True
        for endpoint in self.endpoints.values():
            if endpoint.get('device') is None:
                LOGGER.debug('Need discovery : no device id')
                need = True
            if endpoint.get('in_clusters') is None:
                LOGGER.debug('Need discovery : no clusters list')
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

    def has_template(self):
        typ = self.get_type()
        if not typ:
            LOGGER.warning('No type (modelIdentifier) for device {}'.format(self.addr))
            return
        typ = typ.replace(' ', '_')
        path = os.path.join(BASE_PATH, 'templates', typ + '.json')
        return os.path.exists(path)

    def load_template(self):
        typ = self.get_type()
        if not typ:
            LOGGER.warning('No type (modelIdentifier) for device {}'.format(self.addr))
            return
        typ = typ.replace(' ', '_')
        path = os.path.join(BASE_PATH, 'templates', typ + '.json')
        success = False
        if os.path.exists(path):
            try:
                with open(path) as fp:
                    template = json.load(fp)
                    device = Device.from_json(template)
                    self.update(device)
                success = True
            except Exception:
                LOGGER.error('Failed to load template for {}'.format(typ))
                LOGGER.error(traceback.format_exc())
        else:
            LOGGER.warning('No template found for {}'.format(typ))
        if self.need_report:
            self._bind_report()
        if success:
            self.discovery = 'templated'
            dispatch_signal(ZIGATE_DEVICE_UPDATED,
                            self._zigate, **{'zigate': self._zigate,
                                             'device': self})
        return success

    def generate_template(self, dirname='~'):
        '''
        Generate template file
        '''
        typ = self.get_type()
        if not typ:
            LOGGER.warning('No type (modelIdentifier) for device {}'.format(self.addr))
            return
        typ = typ.replace(' ', '_')
        dirname = os.path.expanduser(dirname)
        path = os.path.join(dirname, typ + '.json')
        jdata = json.dumps(self, cls=DeviceEncoder)
        jdata = json.loads(jdata)
        del jdata['addr']
        del jdata['discovery']
        for key in ('id', 'addr', 'ieee', 'lqi', 'last_seen', 'max_rx', 'max_tx', 'max_buffer'):
            if key in jdata['info']:
                del jdata['info'][key]
        for endpoint in jdata.get('endpoints', []):
            for cluster in endpoint.get('clusters', []):
                cluster_id = cluster['cluster']
                if cluster_id == 0:  # we only keep attribute 4, 5, 7 for cluster 0x0000
                    cluster['attributes'] = [a for a in cluster.get('attributes', [])
                                             if a.get('attribute') in (4, 5, 7)]
                for attribute in cluster.get('attributes', []):
                    keys = list(attribute.keys())
                    for key in keys:
                        if key in ('attribute', 'inverse'):
                            continue
                        if key == 'data' and cluster_id == 0:
                            continue
                        del attribute[key]
        with open(path, 'w') as fp:
            json.dump(jdata, fp, cls=DeviceEncoder,
                      sort_keys=True, indent=4, separators=(',', ': '))

    @property
    def need_report(self):
        return self.info.get('need_report', True)

    def set_assumed_state(self, assumed_state=True):
        self.info['assumed_state'] = assumed_state

    @property
    def assumed_state(self):
        '''
        return True if it has assumed state
        '''
        return self.info.get('assumed_state', False)

    @property
    def groups(self):
        '''
        return groups
        '''
        return self._zigate.get_group_for_addr(self.addr)
