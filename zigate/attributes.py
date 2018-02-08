'''
Created on 8 févr. 2018

@author: sramage
'''
# well known attributes
ATTRIBUTES = {(0x0000, 0x0005): {'friendly_name': 'type', 'value': 'value'},
              (0x0006, 0x0000): {'friendly_name': 'onoff', 'value': 'value'},
              (0x0006, 0x8000): {'friendly_name': 'multiclick', 'value': 'value'},
              (0x0402, 0x0000): {'friendly_name': 'temperature', 'value': 'value/100.', 'unit': '°C'},
              (0x0403, 0x0000): {'friendly_name': 'pressure', 'value': 'value', 'unit': 'mb'},
              (0x0403, 0x0010): {'friendly_name': 'pressure', 'value': 'value/10.', 'unit': 'mb'},
              (0x0405, 0x0000): {'friendly_name': 'humidity', 'value': 'value/100.', 'unit': '%'},
              (0x0406, 0x0000): {'friendly_name': 'presence', 'value': 'value'},
              }
