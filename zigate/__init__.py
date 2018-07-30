#!/usr/bin/env python3

from .core import (ZiGate, ZiGateWiFi)
from .const import *
from pydispatch import dispatcher

__version__ = '0.19.0'

__all__ = ['ZiGate', 'ZiGateWiFi',
           'dispatcher']


def connect(port=None, host=None):
    if host:
        z = ZiGateWiFi(host)
    else:
        z = ZiGate(port)
    return z