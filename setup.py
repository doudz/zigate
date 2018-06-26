#!/usr/bin/env python3
from setuptools import setup
import zigate

setup(
    name='zigate',
    version=zigate.__version__,
    description='python library for the zigate gateway (zigbee) http://zigate.fr',
    long_description=open('README.rst').read(),
    author='Sébastien RAMAGE',
    author_email='sebastien.ramage@gmail.com',
    url='https://github.com/doudz/zigate',
    packages=['zigate'],
    keywords='zigate zigbee python3',
    install_requires=['pyserial', 'pydispatcher'],
    python_requires='>=3',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        "License :: OSI Approved :: MIT License",
    ],
)
