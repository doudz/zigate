#!/usr/bin/env python3
"""
Snipped to dowload current IKEA ZLL OTA files into ~/ota
"""

import os
import json
import urllib.request


def download(otapath):
    print('Download to {}'.format(otapath))
    f = urllib.request.urlopen("http://fw.ota.homesmart.ikea.net/feed/version_info.json")
    data = f.read()

    arr = json.loads(data)

    if not os.path.exists(otapath):
        os.makedirs(otapath)

    for i in arr:
        if 'fw_binary_url' in i:
            url = i['fw_binary_url']
            ls = url.split('/')
            fname = ls[len(ls) - 1]
            path = '%s/%s' % (otapath, fname)

            if not os.path.isfile(path):
                urllib.request.urlretrieve(url, path)
                print(path)
            else:
                print(('%s already exists' % fname))


if __name__ == '__main__':
    BASE_PATH = os.path.expanduser('~')
    otapath = os.path.join(BASE_PATH, 'ota')
    download(otapath)
