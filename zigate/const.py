#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#
import os

# event signal
ZIGATE_DEVICE_ADDED = 'ZIGATE_DEVICE_ADDED'
ZIGATE_DEVICE_UPDATED = 'ZIGATE_DEVICE_UPDATED'
ZIGATE_DEVICE_REMOVED = 'ZIGATE_DEVICE_REMOVED'
ZIGATE_DEVICE_ADDRESS_CHANGED = 'ZIGATE_DEVICE_ADDRESS_CHANGED'
ZIGATE_ATTRIBUTE_ADDED = 'ZIGATE_ATTRIBUTE_ADDED'
ZIGATE_ATTRIBUTE_UPDATED = 'ZIGATE_ATTRIBUTE_UPDATED'
ZIGATE_PACKET_RECEIVED = 'ZIGATE_PACKET_RECEIVED'
ZIGATE_RESPONSE_RECEIVED = 'ZIGATE_RESPONSE_RECEIVED'
ZIGATE_DEVICE_NEED_DISCOVERY = 'ZIGATE_DEVICE_NEED_DISCOVERY'
ZIGATE_FAILED_TO_CONNECT = 'ZIGATE_FAILED_TO_CONNECT'
ZIGATE_CONNECTED = 'ZIGATE_CONNECTED'
ZIGATE_READY = 'ZIGATE_READY'

BATTERY = 0
AC_POWER = 1

TYPE_COORDINATOR = 0
TYPE_ROUTER = 1
TYPE_LEGACY_ROUTER = 2

OFF = 0
ON = 1
TOGGLE = 2
LOCK = 0
UNLOCK = 1
OPEN = 0x00
CLOSE = 0x01
STOP = 0x02
LIFT_VALUE = 0x04
LIFT_PERCENT = 0x05
TILT_VALUE = 0x07
TILT_PERCENT = 0x08

STATUS_CODES = {0: 'Success', 1: 'Invalid parameters',
                2: 'Unhandled command', 3: 'Command failed',
                4: 'Busy', 5: 'Stack already started'}

ACTIONS_ONOFF = 'onoff'
ACTIONS_LEVEL = 'level'
ACTIONS_COLOR = 'color'
ACTIONS_TEMPERATURE = 'temperature'
ACTIONS_HUE = 'hue'
ACTIONS_LOCK = 'lock'
ACTIONS_COVER = 'cover'
ACTIONS_THERMOSTAT = 'thermostat'
ACTIONS_IAS = 'ias'

DATA_TYPE = {0x00: None,
             0x08: 's',  # data8
             0x09: '2s',  # data16
             0x0a: '3s',  # data24
             0x0b: '4s',  # data32
             0x0c: '5s',  # data40
             0x0d: '6s',  # data48
             0x0e: '7s',  # data56
             0x0f: '8s',  # data64
             0x10: '?',  # bool
             0x18: 'b',  # bitmap8
             0x20: 'B',  # uint8
             0x21: 'H',  # uint16
             0x22: 'I',  # uint24
             0x23: 'I',  # uint32
             # 0x24  # uint40
             # 0x25  # uint48
             0x28: 'b',  # int8
             0x29: 'h',  # int16
             0x2a: 'i',  # int24
             0x2b: 'I',  #
             0x30: 'b',  # enum8
             0x38: 'f',  # float semi
             0x39: 'f',  # float simple
             0x3a: 'f',  # float double
             0x41: 's',  # octet string
             0x42: 's',  # char string
             0x43: 's',  # long octet string
             0x44: 's',  # long char string
             }

BASE_PATH = os.path.dirname(__file__)

ADMINPANEL_PORT = 9998
ADMINPANEL_HOST = "0.0.0.0"

