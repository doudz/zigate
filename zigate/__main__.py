#!/usr/bin/env python3
#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#
import logging
import argparse
import time
from zigate import connect
logging.basicConfig()
logging.root.setLevel(logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('--port', help='ZiGate usb port',
                    default=None)
parser.add_argument('--host', help='Wifi ZiGate host:port',
                    default=None)
parser.add_argument('--path', help='ZiGate state file path',
                    default='~/.zigate.json')
parser.add_argument('--gpio', help='Enable PiZigate', default=False, action='store_true')
parser.add_argument('--channel', help='Zigbee channel', default=None)
parser.add_argument('--admin_panel', help='Enable Admin panel', default=True, action='store_true')
args = parser.parse_args()
z = connect(args.port, args.host, args.path, True, True, args.channel, args.gpio)
if args.admin_panel:
    logging.root.info('Starting Admin Panel on port 9998')
    z.start_adminpanel()
print('Press Ctrl+C to quit')
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('Interrupted by user')
z.close()
