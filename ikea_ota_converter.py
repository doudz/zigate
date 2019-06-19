'''
Created on 19 juin 2019

@author: doudz

IKEA OTA files are signed
this script just remove the digital signature
'''
import sys
import struct

path = sys.argv[1]

with open(path, 'rb') as fp:
    data = fp.read()

if not data.startswith(b'NGIS'):
    raise Exception('Not a signed file, no need to convert')

print('Converting', path)
header_end = struct.unpack('<I', data[0x10:0x14])[0]
footer_pos = struct.unpack('<I', data[0x18:0x1C])[0]
data = data[header_end:footer_pos]
with open(path, 'wb') as fp:
    fp.write(data)
print(path, 'converted')
