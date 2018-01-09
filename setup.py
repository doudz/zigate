#!/usr/bin/env python3

from setuptools import setup, find_packages
import zigate
 
setup(
    name='zigate',
    version=zigate.__version__,
    description='python library for the zigate gateway',
    long_description=open('README.md').read(),
    author='Sébastien RAMAGE',
    author_email='sebastien.ramage@gmail.com',
    url='https://github.com/doudz/zigate',
    packages=['zigate'],
    keywords='zigate zigbee',
    install_requires=['pyserial'],
    python_requires='>=3',
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.5',
    ),
)
