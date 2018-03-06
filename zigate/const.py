'''
Created on 12 févr. 2018

@author: sramage
'''

# event signal
ZIGATE_DEVICE_ADDED = 'ZIGATE_DEVICE_ADDED'
ZIGATE_DEVICE_UPDATED = 'ZIGATE_DEVICE_UPDATED'
ZIGATE_DEVICE_REMOVED = 'ZIGATE_DEVICE_REMOVED'
ZIGATE_ATTRIBUTE_ADDED = 'ZIGATE_ATTRIBUTE_ADDED'
ZIGATE_ATTRIBUTE_UPDATED = 'ZIGATE_ATTRIBUTE_UPDATED'
ZIGATE_PACKET_RECEIVED = 'ZIGATE_PACKET_RECEIVED'
ZIGATE_RESPONSE_RECEIVED = 'ZIGATE_RESPONSE_RECEIVED'
ZIGATE_DEVICE_NEED_REFRESH = 'ZIGATE_DEVICE_NEED_REFRESH'

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
