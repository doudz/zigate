#! /usr/bin/python3
#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

TEMPLATES = {
    'lumi.sensor_magnet.aq2': {"endpoints": [
                {
                    "clusters": [
                        {
                            "attributes": [
                                {
                                    "attribute": 0xff01,
                                    "name": "battery",
                                    "unit": "V",
                                }
                            ],
                            "cluster": 0
                        },
                        {
                            "attributes": [
                                {
                                    "attribute": 0,
                                    "name": "onoff",
                                }
                            ],
                            "cluster": 6
                        }
                    ],
                    "device": 0x5f01,
                    "endpoint": 1,
                    "in_clusters": [
                        0x0000,
                        0x0003,
                        0x0006,
                        0xffff
                    ],
                    "out_clusters": [
                        0x0000,
                        0x0004,
                        0xffff
                    ],
                    "profile": 0x0104
                }
            ],
            "info": {
                "bit_field": "0100000000000010",
                "descriptor_capability": "00000000",
                "mac_capability": "10000000",
                "manufacturer_code": "1037",
                "power_type": 0,
                "server_mask": 0
            }}
    }
