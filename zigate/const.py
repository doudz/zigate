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

STATUS_CODES = {0: 'Success', 1: 'Invalid parameters',
                2: 'Unhandled command', 3: 'Command failed',
                4: 'Busy', 5: 'Stack already started'}

ACTIONS_ONOFF = 'onoff'
ACTIONS_LEVEL = 'level'
ACTIONS_COLOR = 'color'
ACTIONS_TEMPERATURE = 'temperature'
ACTIONS_HUE = 'hue'
ACTIONS_LOCK = 'lock'

DATA_TYPE = {0x00: None,
             0x10: '?',  # bool
             0x18: 'b',
             0x20: 'B',
             0x21: 'H',
             0x22: 'I',
             0x23: 'I',
             0x28: 'b',
             0x29: 'h',
             0x2a: 'i',
             0x30: 'b',
             0x39: 'f',
             0x41: 's',
             0x42: 's',
             }

BASE_PATH = os.path.dirname(__file__)
