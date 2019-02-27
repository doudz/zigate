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
with open(version_path) as version_file:
    exec(version_file.read(), main_ns)

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

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

    install_requires=[
        'pyserial',
        'pydispatcher',
        'bottle',
        'RPi.GPIO'
    ],
    extras_require={
        'dev': ['tox'],
        'mqtt': ['paho-mqtt']
    },
    python_requires='>=3',

    project_urls={
        'Bug Reports': 'https://github.com/doudz/zigate/issues',
        'Source': 'https://github.com/doudz/zigate/',
    },
    test_suite='tests',
)
