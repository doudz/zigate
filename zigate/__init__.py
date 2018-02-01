#!/usr/bin/env python3

from .core import (ZiGate, ZiGateWiFi,
                   ZGT_CMD_NEW_DEVICE,
                   ZGT_CMD_REMOVE_DEVICE,
                   ZGT_CMD_DEVICE_UPDATE)

__version__ = '0.6.0'

__all__ = ['__version__', 'ZiGate', 'ZiGateWiFi',
           'ZGT_CMD_NEW_DEVICE', 'ZGT_CMD_REMOVE_DEVICE',
           'ZGT_CMD_DEVICE_UPDATE'
           ]
