#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import zigate

# Setup part
setup(
    name='zigate',
    version=zigate.__version__,
    description='python library for the zigate gateway (zigbee) http://zigate.fr',
    long_description=open('README.rst').read(),
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

    install_requires=[
        'pyserial',
        'pydispatcher'
    ],
    extras_require={
        'dev': ['tox']
    },
    python_requires='>=3',

    project_urls={
        'Bug Reports': 'https://github.com/doudz/zigate/issues',
        'Source': 'https://github.com/doudz/zigate/',
    },
)
