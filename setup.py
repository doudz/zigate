#!/usr/bin/env python3
#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

"""
zigate, setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup
from distutils.util import convert_path
from os import path

here = path.abspath(path.dirname(__file__))

# Get __version without load zigate module
main_ns = {}
version_path = convert_path('zigate/version.py')
with open(version_path, encoding='utf-8') as version_file:
    exec(version_file.read(), main_ns)

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


# extracted from https://raspberrypi.stackexchange.com/questions/5100/detect-that-a-python-program-is-running-on-the-pi
def is_raspberry_pi(raise_on_errors=False):
    """Checks if Raspberry PI.

    :return:
    """
    try:
        with open('/proc/cpuinfo', 'r') as cpuinfo:
            found = False
            for line in cpuinfo:
                if line.startswith('Hardware'):
                    found = True
                    label, value = line.strip().split(':', 1)
                    value = value.strip()
                    if value not in (
                        'BCM2708',
                        'BCM2709',
                        'BCM2835',
                        'BCM2836'
                    ):
                        if raise_on_errors:
                            raise ValueError(
                                'This system does not appear to be a '
                                'Raspberry Pi.'
                            )
                        else:
                            return False
            if not found:
                if raise_on_errors:
                    raise ValueError(
                        'Unable to determine if this system is a Raspberry Pi.'
                    )
                else:
                    return False
    except IOError:
        if raise_on_errors:
            raise ValueError('Unable to open `/proc/cpuinfo`.')
        else:
            return False

    return True


requires = ['pyserial>=3.2',
            'pydispatcher>=2.0.5',
            'pyusb',
            'bottle',
            'requests'
            ]
if is_raspberry_pi():
    requires.append('RPi.GPIO')

# Setup part
setup(
    name='zigate',
    version=main_ns['__version__'],
    description='python library for the zigate gateway (zigbee) http://zigate.fr',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/doudz/zigate',
    author='Sébastien RAMAGE',
    author_email='sebastien.ramage@gmail.com',

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
    ],

    keywords='zigate zigbee python3',
    packages=['zigate'],
    include_package_data=True,

    install_requires=requires,
    extras_require={
        'dev': ['tox'],
        'mqtt': ['paho-mqtt']
    },
    python_requires='>=3.5',

    project_urls={
        'Bug Reports': 'https://github.com/doudz/zigate/issues',
        'Source': 'https://github.com/doudz/zigate/',
    },
    test_suite='tests',
)
