'''
Created on 12 août 2019

@author: doudz
'''
import requests
import logging
import os
from collections import OrderedDict

URL = 'https://api.github.com/repos/fairecasoimeme/ZiGate/releases'
LOGGER = logging.getLogger('zigate')


def get_releases():
    LOGGER.info('Searching for ZiGate firmware')
    releases = OrderedDict()
    r = requests.get(URL)
    if r.status_code == 200:
        for release in r.json():
            if release.get('draft'):
                LOGGER.debug('ignoring draft %s', release['name'])
                continue
            if release.get('prerelease'):
                LOGGER.debug('ignoring prerelease %s', release['name'])
                continue
            for asset in release['assets']:
                if 'pdmhost' in asset['name'].lower():
                    LOGGER.debug('ignoring pdm on host firmware %s', release['name'])
                    continue
                if asset['name'].endswith('.bin'):
                    LOGGER.info('Found %s', asset['name'])
                    releases[asset['name']] = asset['browser_download_url']
    return releases


def download(url, dest='/tmp'):
    filename = url.rsplit('/', 1)[1]
    LOGGER.info('Downloading %s to %s', url, dest)
    r = requests.get(url, allow_redirects=True)
    filename = os.path.join(dest, filename)
    with open(filename, 'wb') as fp:
        fp.write(r.content)
    LOGGER.info('Done')
    return filename


def download_latest(dest='/tmp'):
    LOGGER.info('Download latest firmware')
    releases = get_releases()
    LOGGER.debug('Available firmwares %s', releases)
    if releases:
        latest = list(releases.keys())[0]
        LOGGER.info('Latest is %s', latest)
        return download(releases[latest], dest)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    download_latest()
