#!/usr/bin/python3
#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#
# Thanks to Sander Hoentjen (tjikkun) we now have a flasher !
# https://github.com/tjikkun/zigate-flasher

import argparse
import atexit
import functools
import itertools
import logging
import struct
from operator import xor
import datetime
from .firmware import download_latest
from .transport import discover_port
import time
import serial
from serial.tools.list_ports import comports
try:
    import RPi.GPIO as GPIO
except Exception:
    # Fake GPIO
    class GPIO:
        def fake(self, *args, **kwargs):
            pass

        def __getattr__(self, *args, **kwargs):
            return self.fake
    GPIO = GPIO()
import usb


logger = logging.getLogger('ZiGate Flasher')
_responses = {}

ZIGATE_CHIP_ID = 0x10408686
ZIGATE_BINARY_VERSION = bytes.fromhex('07030008')
ZIGATE_FLASH_START = 0x00000000
ZIGATE_FLASH_END = 0x00040000


class Command:

    def __init__(self, type_, fmt=None, raw=False):
        assert not (raw and fmt), 'Raw commands cannot use built-in struct formatting'
        logger.debug('Command {} {} {}'.format(type_, fmt, raw))
        self.type = type_
        self.raw = raw
        if fmt:
            self.struct = struct.Struct(fmt)
        else:
            self.struct = None

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            rv = func(*args, **kwargs)

            if self.struct:
                try:
                    data = self.struct.pack(*rv)
                except TypeError:
                    data = self.struct.pack(rv)
            elif self.raw:
                data = rv
            else:
                data = bytearray()

            return prepare(self.type, data)

        return wrapper


class Response:

    def __init__(self, type_, data, chksum):
        logger.debug('Response {} {} {}'.format(type_, data, chksum))
        self.type = type_
        self.data = data[1:]
        self.chksum = chksum
        self.status = data[0]

    @property
    def ok(self):
        return self.status == 0

    def __str__(self):
        return 'Response(type=0x%02x, data=0x%s, checksum=0x%02x)' % (self.type,
                                                                      self.data.hex(),
                                                                      self.chksum)


def register(type_):
    assert type_ not in _responses, 'Duplicate response type 0x%02x' % type_

    def decorator(func):
        _responses[type_] = func
        return func

    return decorator


def prepare(type_, data):
    length = len(data) + 2

    checksum = functools.reduce(xor,
                                itertools.chain(type_.to_bytes(2, 'big'),
                                                length.to_bytes(2, 'big'),
                                                data), 0)

    message = struct.pack('!BB%dsB' % len(data), length, type_, data, checksum)
    # print('Prepared command 0x%s' % message.hex())
    return message


def read_response(ser):
    length = ser.read()
    length = int.from_bytes(length, 'big')
    logger.debug('read_response length {}'.format(length))
    answer = ser.read(length)
    logger.debug('read_response answer {}'.format(answer))
    return _unpack_raw_message(length, answer)
    # type_, data, chksum = struct.unpack('!B%dsB' % (length - 2), answer)
    # return {'type': type_, 'data': data, 'chksum': chksum}


def _unpack_raw_message(length, decoded):
    logger.debug('unpack raw message {} {}'.format(length, decoded))
    if len(decoded) != length or length < 2:
        logger.exception("Unpack failed, length: %d, msg %s" % (length, decoded.hex()))
        return
    type_, data, chksum = \
        struct.unpack('!B%dsB' % (length - 2), decoded)
    return _responses.get(type_, Response)(type_, data, chksum)


@Command(0x07)
def req_flash_erase():
    pass


@Command(0x09, raw=True)
def req_flash_write(addr, data):
    msg = struct.pack('<L%ds' % len(data), addr, data)
    return msg


@Command(0x0b, '<LH')
def req_flash_read(addr, length):
    return (addr, length)


@Command(0x1f, '<LH')
def req_ram_read(addr, length):
    return (addr, length)


@Command(0x25)
def req_flash_id():
    pass


@Command(0x27, '!B')
def req_change_baudrate(rate):
    # print(serial.Serial.BAUDRATES)
    clockspeed = 1000000
    divisor = round(clockspeed / rate)
    # print(divisor)
    return divisor


@Command(0x2c, '<BL')
def req_select_flash_type(type_, custom_jump=0):
    return (type_, custom_jump)


@Command(0x32)
def req_chip_id():
    pass


@Command(0x36, 'B')
def req_eeprom_erase(pdm_only=False):
    return not pdm_only


@register(0x26)
class ReadFlashIDResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)
        self.manufacturer_id, self.device_id = struct.unpack('!BB', self.data)

    def __str__(self):
        return 'ReadFlashIDResponse %d (ok=%s, manufacturer_id=0x%02x, device_id=0x%02x)' % (self.status,
                                                                                             self.ok,
                                                                                             self.manufacturer_id,
                                                                                             self.device_id)


@register(0x28)
class ChangeBaudrateResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)

    def __str__(self):
        return 'ChangeBaudrateResponse %d (ok=%s)' % (self.status, self.ok)


@register(0x33)
class GetChipIDResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)
        (self.chip_id,) = struct.unpack('!L', self.data)

    def __str__(self):
        return 'GetChipIDResponse (ok=%s, chip_id=0x%04x)' % (self.ok, self.chip_id)


@register(0x37)
class EraseEEPROMResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)

    def __str__(self):
        return 'EraseEEPROMResponse %d (ok=%s)' % (self.status, self.ok)


def change_baudrate(ser, baudrate):
    ser.write(req_change_baudrate(baudrate))

    res = read_response(ser)
    if not res or not res.ok:
        logger.exception('Change baudrate failed')
        raise SystemExit(1)

    ser.baudrate = baudrate


def check_chip_id(ser):
    ser.write(req_chip_id())
    res = read_response(ser)
    if not res or not res.ok:
        logger.exception('Getting Chip ID failed')
        raise SystemExit(1)
    if res.chip_id != ZIGATE_CHIP_ID:
        logger.exception('This is not a supported chip, patches welcome')
        raise SystemExit(1)


def get_flash_type(ser):
    ser.write(req_flash_id())
    res = read_response(ser)

    if not res or not res.ok:
        print('Getting Flash ID failed')
        raise SystemExit(1)

    if res.manufacturer_id != 0xcc or res.device_id != 0xee:
        print('Unsupported Flash ID, patches welcome')
        raise SystemExit(1)
    else:
        return 8


def get_mac(ser):
    ser.write(req_ram_read(0x01001570, 8))
    res = read_response(ser)
    if res.data == bytes.fromhex('ffffffffffffffff'):
        ser.write(req_ram_read(0x01001580, 8))
        res = read_response(ser)
    return ':'.join(''.join(x) for x in zip(*[iter(res.data.hex())] * 2))


def select_flash(ser, flash_type):
    ser.write(req_select_flash_type(flash_type))
    res = read_response(ser)
    if not res or not res.ok:
        print('Selecting flash type failed')
        raise SystemExit(1)


def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r{0} |{1}| {2}% {3}'.format(prefix, bar, percent, suffix), end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()


def write_flash_to_file(ser, filename):
    # flash_start = cur = ZIGATE_FLASH_START
    cur = ZIGATE_FLASH_START
    flash_end = ZIGATE_FLASH_END

    logger.info('Backup firmware to %s', filename)
    with open(filename, 'wb') as fd:
        fd.write(ZIGATE_BINARY_VERSION)
        read_bytes = 128
        while cur < flash_end:
            if cur + read_bytes > flash_end:
                read_bytes = flash_end - cur
            ser.write(req_flash_read(cur, read_bytes))
            res = read_response(ser)
            if not res or not res.ok:
                print('Reading flash failed')
                raise SystemExit(1)
            if cur == 0:
                (flash_end,) = struct.unpack('>L', res.data[0x20:0x24])
            fd.write(res.data)
            printProgressBar(cur, flash_end, 'Reading')
            cur += read_bytes
    printProgressBar(flash_end, flash_end, 'Reading')
    logger.info('Backup firmware done')


def write_file_to_flash(ser, filename):
    logger.info('Writing new firmware from %s', filename)
    with open(filename, 'rb') as fd:
        ser.write(req_flash_erase())
        res = read_response(ser)
        if not res or not res.ok:
            print('Erasing flash failed')
            raise SystemExit(1)

        # flash_start = cur = ZIGATE_FLASH_START
        cur = ZIGATE_FLASH_START
        flash_end = ZIGATE_FLASH_END

        bin_ver = fd.read(4)
        if bin_ver != ZIGATE_BINARY_VERSION:
            print('Not a valid image for Zigate')
            raise SystemExit(1)
        read_bytes = 128
        while cur < flash_end:
            data = fd.read(read_bytes)
            if not data:
                break
            ser.write(req_flash_write(cur, data))
            res = read_response(ser)
            if not res.ok:
                print('writing failed at 0x%08x, status: 0x%x, data: %s' % (cur, res.status, data.hex()))
                raise SystemExit(1)
            printProgressBar(cur, flash_end, 'Writing')
            cur += read_bytes
    printProgressBar(flash_end, flash_end, 'Writing')
    logger.info('Writing new firmware done')


def erase_EEPROM(ser, pdm_only=False):
    ser.timeout = 10  # increase timeout because official NXP programmer do it
    ser.write(req_eeprom_erase(pdm_only))
    res = read_response(ser)
    if not res or not res.ok:
        print('Erasing EEPROM failed')
        raise SystemExit(1)


def flash(serialport='auto', write=None, save=None, erase=False, pdm_only=False):
    """
    Read or write firmware
    """
    serialport = discover_port(serialport)
    try:
        ser = serial.Serial(serialport, 38400, timeout=5)
    except serial.SerialException:
        logger.exception("Could not open serial device %s", serialport)
        return

    change_baudrate(ser, 115200)
    check_chip_id(ser)
    flash_type = get_flash_type(ser)
    mac_address = get_mac(ser)
    logger.info('Found MAC-address: %s', mac_address)
    if write or save or erase:
        select_flash(ser, flash_type)

    if save:
        write_flash_to_file(ser, save)

    if write:
        write_file_to_flash(ser, write)

    if erase:
        erase_EEPROM(ser, pdm_only)
    change_baudrate(ser, 38400)
    ser.close()


def upgrade_firmware(port):
    backup_filename = 'zigate_backup_{:%Y%m%d%H%M%S}.bin'.format(datetime.datetime.now())
    flash(port, save=backup_filename)
    print('ZiGate backup created {}'.format(backup_filename))
    firmware_path = download_latest()
    print('Firmware downloaded', firmware_path)
    flash(port, write=firmware_path)
    print('ZiGate flashed with {}'.format(firmware_path))


def ftdi_set_bitmode(dev, bitmask):
    '''
    Set mode for ZiGate DIN module
    '''
    BITMODE_CBUS = 0x20
    SIO_SET_BITMODE_REQUEST = 0x0b
    bmRequestType = usb.util.build_request_type(usb.util.CTRL_OUT,
                                                usb.util.CTRL_TYPE_VENDOR,
                                                usb.util.CTRL_RECIPIENT_DEVICE)
    wValue = bitmask | (BITMODE_CBUS << BITMODE_CBUS)
    dev.ctrl_transfer(bmRequestType, SIO_SET_BITMODE_REQUEST, wValue)


def main():
    ports_available = [port for (port, _, _) in sorted(comports())]
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--serialport', choices=ports_available,
                        help='Serial port, e.g. /dev/ttyUSB0', required=True)
    parser.add_argument('-w', '--write', help='Firmware bin to flash onto the chip')
    parser.add_argument('-s', '--save', help='File to save the currently loaded firmware to')
    parser.add_argument('-u', '--upgrade', help='Download and flash the lastest available firmware',
                        action='store_true', default=False)
#     parser.add_argument('-e', '--erase', help='Erase EEPROM', action='store_true')
#     parser.add_argument('--pdm-only', help='Erase PDM only, use it with --erase', action='store_true')
    parser.add_argument('-d', '--debug', help='Set log level to DEBUG', action='store_true')
    parser.add_argument('--gpio', help='Configure GPIO for PiZiGate flash', action='store_true', default=False)
    parser.add_argument('--din', help='Configure USB for ZiGate DIN flash', action='store_true', default=False)
    args = parser.parse_args()
    logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.gpio:
        logger.info('Put PiZiGate in flash mode')
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(27, GPIO.OUT)  # GPIO2
        GPIO.output(27, GPIO.LOW)  # GPIO2
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # GPIO0
        time.sleep(0.5)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # GPIO0
        time.sleep(0.5)
    elif args.din:
        logger.info('Put ZiGate DIN in flash mode')
        dev = usb.core.find(idVendor=0x0403, idProduct=0x6001)
        if not dev:
            logger.error('ZiGate DIN not found.')
            return
        ftdi_set_bitmode(dev, 0x00)
        time.sleep(0.5)
        # Set CBUS2/3 high...
        ftdi_set_bitmode(dev, 0xCC)
        time.sleep(0.5)
        # Set CBUS2/3 low...
        ftdi_set_bitmode(dev, 0xC0)
        time.sleep(0.5)
        ftdi_set_bitmode(dev, 0xC4)
        time.sleep(0.5)
        # Set CBUS2/3 back to tristate
        ftdi_set_bitmode(dev, 0xCC)
        time.sleep(0.5)

    if args.upgrade:
        upgrade_firmware(args.serialport)

    else:
        try:
            ser = serial.Serial(args.serialport, 38400, timeout=5)
        except serial.SerialException:
            logger.exception("Could not open serial device %s", args.serialport)
            raise SystemExit(1)

        # atexit.register(change_baudrate, ser, 38400)

        change_baudrate(ser, 115200)
        check_chip_id(ser)
        flash_type = get_flash_type(ser)
        mac_address = get_mac(ser)
        logger.info('Found MAC-address: %s', mac_address)
        if args.write or args.save:  # or args.erase:
            select_flash(ser, flash_type)

        if args.save:
            write_flash_to_file(ser, args.save)

        if args.write:
            write_file_to_flash(ser, args.write)

#         if args.erase:
#             erase_EEPROM(ser, args.pdm_only)


    if args.gpio:
        logger.info('Put PiZiGate in running mode')
        GPIO.output(27, GPIO.HIGH)  # GPIO2
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # GPIO0
        time.sleep(0.5)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # GPIO0
        time.sleep(0.5)
    elif args.din:
        logger.info('Put ZiGate DIN in running mode')
        ftdi_set_bitmode(dev, 0xC8)
        time.sleep(0.5)
        ftdi_set_bitmode(dev, 0xCC)
        time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig()
    main()
