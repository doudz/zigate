#!/usr/bin/env python3

from .core import (ZiGate, ZiGateWiFi,
                   ZIGATE_DEVICE_ADDED,
                   ZIGATE_DEVICE_UPDATED,
                   ZIGATE_DEVICE_REMOVED,
                   ZIGATE_ATTRIBUTE_ADDED,
                   ZIGATE_ATTRIBUTE_UPDATED)

__version__ = '0.7.3'

__all__ = ['__version__', 'ZiGate', 'ZiGateWiFi',
           'ZIGATE_DEVICE_ADDED', 'ZIGATE_DEVICE_UPDATED',
           'ZIGATE_DEVICE_REMOVED', "ZIGATE_ATTRIBUTE_ADDED",
           "ZIGATE_ATTRIBUTE_UPDATED"
           ]
