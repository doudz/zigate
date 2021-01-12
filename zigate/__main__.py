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
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', help='Debug',
                    default=False, action='store_true')
parser.add_argument('--port', help='ZiGate usb port',
                    default=None)
parser.add_argument('--host', help='Wifi ZiGate host:port',
                    default=None)
parser.add_argument('--path', help='ZiGate state file path',
                    default='~/.zigate.json')
parser.add_argument('--gpio', help='Enable PiZigate', default=False, action='store_true')
parser.add_argument('--channel', help='Zigbee channel', default=None)
parser.add_argument('--admin_panel', help='Enable Admin panel', default=True, action='store_true')
parser.add_argument('--admin_panel_port', help='Admin panel url prefix', default=9998)
parser.add_argument('--admin_panel_host', help='Admin panel url prefix', default="0.0.0.0")
parser.add_argument('--admin_panel_mount', help='Admin panel url mount point', default=None)
parser.add_argument('--admin_panel_prefix', help='Admin panel url prefix', default=None)
args = parser.parse_args()
if args.debug:
    logging.root.setLevel(logging.DEBUG)
z = connect(args.port, args.host, args.path, True, True, args.channel, args.gpio)
if args.admin_panel:
    logging.root.info('Starting Admin Panel on %s:%s', args.admin_panel_host, args.admin_panel_port)
    if args.admin_panel_mount:
        logging.root.info('Mount point is %s', args.admin_panel_mount)
    if args.admin_panel_prefix:
        logging.root.info('URL prefix is %s', args.admin_panel_prefix)
    z.start_adminpanel(port=int(args.admin_panel_port), host=args.admin_panel_host, mount=args.admin_panel_mount, prefix=args.admin_panel_prefix,
                       debug=args.debug)
print('Press Ctrl+C to quit')
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('Interrupted by user')
z.save_state()
z.close()
